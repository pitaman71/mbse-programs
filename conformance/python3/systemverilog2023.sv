// A cold-chain logger's datapath and its testbench: every construct of the design subset of SystemVerilog and of its
// classes, in IEEE 1800-2023.
`resetall
`timescale 1ns / 1ps
`default_nettype none
`define WIDTH 16

`ifdef SIMULATION
`define CHECKS 1
`elsif FPGA
`define CHECKS 2
`else
`define CHECKS 0
`endif

`undef CHECKS
`include "defs.svh"

/* The packet's fields, as the interface control document specifies them. */
package logger_pkg;
    parameter int unsigned FIELDS = 3;
    localparam logic [7:0] BATTERY_LOW = 8'b0000_0100;
    typedef enum logic [1:0] {IDLE, SAMPLE, SEND = 2'd3} state_t;
    typedef struct packed {
        logic signed [15:0] raw;
        logic [7:0] status;
    } reading_t;
    typedef logic [7:0] byte_t;
    typedef byte_t queue_t[$];

    function automatic logic in_range(input logic signed [15:0] raw, input int lo = 200, hi = 800);
        return raw >= lo && raw <= hi;
    endfunction

    task automatic wait_cycles(input int n);
        repeat (n) @(posedge tb.clk);
    endtask
endpackage

interface bus_if #(
    parameter int W = 8
) (
    input logic clk
);
    logic [W - 1:0] data;
    logic valid, ready;
    modport source (output data, output valid, input ready);
    modport sink (input data, input valid, output ready);
endinterface

module sampler
    import logger_pkg::*;
#(
    parameter int WIDTH = `WIDTH,
    parameter type T = reading_t,
    localparam int DEPTH = 4
) (
    input wire clk,
    input wire rst_n,
    input T reading,
    bus_if.source out,
    output logic [WIDTH - 1:0] count,
    output state_t state
);
    import logger_pkg::in_range;
    wire [3:0] nibble = reading.raw[3:0];
    logic [7:0] history[DEPTH];
    logic signed [WIDTH - 1:0] sum;
    int unsigned samples;
    real average = 0.0;
    string name = "sampler";
    byte_t lookup[string];
    integer i;
    genvar g;
    state_t state_next;
    logic [3:0] nibble2;
    event done;
    logic [7:0] dynamic[];
    logger_pkg::queue_t pending;
    assign out.data = reading.status;
    assign #2 out.valid = state == SEND && !out.ready ? 1'b1 : 1'b0;

    always_ff @(posedge clk or negedge rst_n) begin : counter
        if (!rst_n) begin
            count <= '0;
            state <= IDLE;
        end else if (reading.status & BATTERY_LOW) begin
            count <= count + 1'b1;
        end else begin
            count <= {count[WIDTH - 2:0], 1'b0};
        end
    end : counter

    always_comb begin
        sum = '0;
        for (int k = 0; k < DEPTH; k++) begin
            sum += signed'(16'(history[k]));
        end
        unique case (state)
            IDLE: state_next = SAMPLE;
            SAMPLE, SEND: begin
                state_next = in_range(reading.raw) ? SEND : IDLE;
            end
            default: state_next = IDLE;
        endcase
    end

    always_latch
        if (out.ready)
            samples = samples + 1;

    always @(*) begin
        priority casez (reading.status)
            8'b1???_????: average = real'(sum) / DEPTH;
            8'b01??_????: average = 1.5e3;
            default: ;
        endcase
    end

    generate
        for (g = 0; g < DEPTH; g = g + 1) begin : stage
            always_ff @(posedge clk) history[g] <= g == 0 ? reading.raw[7:0] : history[g - 1];
        end
    endgenerate

    if (WIDTH > 8) begin : wide
        assign nibble2 = {2{reading.raw[WIDTH - 1 -: 2]}};
    end else begin : narrow
        assign nibble2 = reading.raw[0 +: 4];
    end

    case (DEPTH)
        4: begin : four
            localparam int HALF = DEPTH / 2;
        end
        default: begin : other
        end
    endcase

    bus_if #(.W(8)) monitor (.clk(clk));
    counter #(WIDTH, 1) u_counter (.clk, .rst_n(rst_n), .count());
    checker_unit u_check (.*);
    fifo #(.DEPTH(DEPTH)) u_fifo[1:0] (clk, rst_n, out.data);

    initial begin
        lookup["idle"] = 8'hFF;
        lookup.delete("idle");
        i = 0;
        while (i < 4)
            i++;
        do
            i--;
        while (i > 0);
        forever begin
            #10ns;
            @(posedge clk iff rst_n);
            if (count === 'x)
                break;
            if (count !== 'z)
                continue;
            wait (out.ready) -> done;
        end
        foreach (history[j])
            history[j] = 8'h00;
        fork
            #5 $display("a %0d", count);
            begin
                @(negedge clk);
            end
        join_none
        assert (count inside {[0:15], 20}) else $error("count %0d out of range", count);
        assert #0 (state != SEND || out.ready);
        sum = '{default: 0} == 0 ? 16'sd5 : -16'sd5;
        {sum[15:8], sum[7:0]} = {8'd1, 8'd2};
        sum <<= 1;
        sum = sum >>> 1 ** 2 % 3;
        samples = $clog2(DEPTH) + $bits(sum) + (count ~^ 8'hA5) + &count + |count + ^count;
        i = int'(average) <-> i;
        disable counter;
        samples = logger_pkg::FIELDS + pending[$];
        $finish;
    end

    final
        $display("done");
endmodule

module counter #(
    parameter WIDTH = 4, STEP = 1
) (clk, rst_n, count);
    input clk, rst_n;
    output reg [WIDTH - 1:0] count;

    always @(posedge clk)
        if (rst_n == 1'b0)
            count = 0;
        else
            count = #1 count + STEP;
endmodule

program automatic test_program (
    input logic clk
);
    initial begin
        repeat (3) @(posedge clk);
        $display("time %t", $time);
    end
endprogram

// The testbench's transactions and drivers.
package logger_tb_pkg;
    import logger_pkg::*;
    typedef class driver;

    interface class sink #(
        type T = reading_t
    );
        pure virtual function void put(T item);
    endclass

    virtual class transaction #(
        int W = 16
    ) implements sink #(reading_t);
        rand bit [W - 1:0] raw;
        randc logic [7:0] status;
        local static int count = 0;
        protected int id;
        extern function new(int id = 0);
        pure virtual function transaction #(W) copy;

        virtual function void put(reading_t item);
            raw = item.raw;
        endfunction
    endclass : transaction

    function transaction::new(int id = 0);
        this.id = id;
        count++;
    endfunction

    class sample extends transaction #(16);
        byte history[];

        function new(int id);
            super.new(id);
            history = new[4];
        endfunction

        virtual function transaction #(16) copy;
            sample other = new this;
            other.history = new[8](history);
            return other;
        endfunction
    endclass

    class driver;
        virtual bus_if.source bus;
        sample current = null;

        function new(virtual bus_if.source bus);
            this.bus = bus;
            current = logger_tb_pkg::sample::new(1);
        endfunction
    endclass
endpackage
