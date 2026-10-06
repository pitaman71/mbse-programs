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
// The cold room's temperature, for the compilation unit.
real ambient = 4.0;

/* The packet's fields, as the interface control document specifies them. */
package logger_pkg;
    timeunit 1ns / 1ps;
    parameter int unsigned FIELDS = 3;
    localparam logic [7:0] BATTERY_LOW = 8'b0000_0100;
    typedef enum logic [1:0] {IDLE, SAMPLE, SEND = 2'd3} state_t;
    typedef enum {PROBE[2], BAY[1:3] = 5} source_t;
    typedef struct packed {
        logic signed [15:0] raw;
        logic [7:0] status;
    } reading_t;
    typedef logic [7:0] byte_t;
    typedef byte_t queue_t[$];

    function automatic logic in_range(input logic signed [15:0] raw, input int lo = 200, hi = 800);
        return raw >= lo && raw <= hi;
    endfunction

    // The probe's current, which its drivers add.
    function automatic real sum_currents(input real drivers[]);
        return drivers[0] + drivers[1];
    endfunction

    nettype real current_t with sum_currents;
    export "DPI-C" sum_c = function sum_currents;
    import "DPI-C" pure function real c_sqrt(input real x);
    import "DPI-C" context task c_log(input string message);
    nettype logic [1:0] level_t;
    export *::*;

    function automatic void tally(const ref int total, ref static int seen);
        seen += total;
    endfunction

    // A reading in its band, checked wherever it is.
    checker in_band(input real level, input logic clk);
        assert property (@(posedge clk) level > 0.0);
    endchecker

    task automatic wait_cycles(input int n);
        repeat (n) @(posedge tb.clk);
    endtask
endpackage

interface bus_if #(
    parameter int W = 8
) (
    input logic clk
);
    timeunit 1ns;
    timeprecision 1ps;
    typedef logic [W - 1:0] word_t;
    logic [W - 1:0] data;
    logic valid, ready;
    modport source (output data, output valid, input ready);
    modport sink (input data, input valid, output ready);

    clocking cb @(posedge clk);
        input data;
    endclocking

    task automatic pulse;
        valid = 1'b1;
    endtask

    modport bench (clocking cb, import pulse, import task settle(int n), export probe, input .seen(valid), output .spare());
endinterface

module sampler
    import logger_pkg::*;
#(
    parameter int WIDTH = `WIDTH,
    parameter type T = reading_t,
    parameter type enum S = state_t,
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
    (* keep, max_fanout = 8 *) wire [3:0] nibble = reading.raw[3:0];
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
    wire #(1, 2, 3) settled = nibble2[0];
    wire (strong0, pull1) vectored [3:0] driven = nibble2;
    trireg (medium) held;
    tri scalared [1:0] pair;
    level_t #1 levels;
    wire [1:0] low_pair;
    var type(nibble2) shadow;
    event done;
    logic [7:0] dynamic[];
    logger_pkg::queue_t pending;
    typedef out.word_t word_t;
    logic [3:0] grid[2][2];
    assign out.data = reading.status;
    assign #2 out.valid = state == SEND && !out.ready ? 1'b1 : 1'b0;
    assign (weak0, weak1) #1 pair = nibble2[1:0];
    alias low_pair = pair;
    defparam u_counter.STEP = 2;

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
        (* parallel_case *) priority casez (reading.status)
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

    if (DEPTH < 2)
        $error("DEPTH is %0d, below 2", DEPTH);
    else
        $info;

    counter #(WIDTH, 1) u_counter (.clk, .rst_n(rst_n), .count());
    checker_unit u_check (.*);
    logger_pkg::in_band band_check (average, clk);

    always @(posedge clk) begin
        checker_unit u_watch (clk, count);
        logger_pkg::in_band step_check (average, clk);
    end

    fifo #(.DEPTH(DEPTH)) u_fifo[1:0] (clk, rst_n, out.data);
    fifo spare (clk, , out.data);

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
        foreach (grid[, col])
            grid[0][col] = '0;
        fork
            #5 $display("a %0d", count);
            begin
                @(negedge clk);
            end
        join_none
        assert (count inside {[0:15], 20}) else $error("count %0d out of range", count);
        assert #0 (state != SEND || out.ready);
        sum = '{default: 0} == 0 ? (* likely *) 16'sd5 : - (* rare *) 16'sd5 + (* fold *) $bits (* folded *) (sum);
        {sum[15:8], sum[7:0]} = {8'd1, 8'd2};
        sum <<= 1;
        sum = sum >>> 1 ** 2 % 3;
        samples = $clog2(DEPTH) + $bits(sum) + (count ~^ 8'hA5) + &count + |count + ^count;
        i = int'(average) <-> i;
        disable counter;
        force out.valid = 1'b0;
        release out.valid;
        assign samples = 0;
        deassign samples;
        ->> #1 done;
        ->> @(posedge clk) done;
        sum <= repeat (2) @(posedge clk) '0;
        samples = logger_pkg::FIELDS + pending[$];
        pending = {};
        lookup["packed"] = {>>{reading.raw, reading.status}} + {<< byte {history with [0 +: 2]}} + {>> 4 {history with [1]}};
        history = '{DEPTH{8'h00}};
        #(1:2:3) average = $unit::ambient + (2:3:4);
        if (average inside {[20.0 +/- 2.5], [4.0 +%- 10.0]})
            $display("in band", , average);
        samples = $root.sampler.samples + type(samples)'(1);
        $finish;
    end

    final
        $display("done");

`ifdef (SIMULATION && !FPGA || TRACE -> SIMULATION)
    initial
        $display("traced");
`elsif (FPGA)
    initial $display("on the board");
`endif

    // The datapath's properties, checked on every clock.
    default clocking sample_clk @(posedge clk);
        default input #1step output #0;
        input reading, count;
        output negedge #1 flush;
        input #1 output #2 state_probe = state;
    endclocking : sample_clk

    default disable iff (!rst_n);
    let in_band(v, lo = 200, hi = 800) = v >= lo && v <= hi;

    sequence sent(local input int n = 1);
        int seen;
        (state == SEND, seen = n) ##1 out.ready[->1] ##[1:3] !out.valid;
    endsequence : sent

    sequence burst;
        @(posedge clk) out.valid[*2:4] ##1 (out.ready throughout out.valid[*1:$]) intersect first_match(##[0:$] !out.valid) or reading.status[=1] and sent(2) within out.valid ##[1:$] out.ready[*1:$];
    endsequence

    property counts(sequence s, untyped bound);
        @(posedge clk) disable iff (!rst_n) s |=> count < bound and s_eventually [1:4] state == IDLE;
    endproperty

    property stays_in_band;
        if (state == SAMPLE) strong(in_band(reading.raw)) else weak(1'b1) implies nexttime [2] state != SEND iff always [0:3] rst_n;
    endproperty

    property safe;
        accept_on (!rst_n) (not out.valid until out.ready) or reject_on (state == SEND) count s_until_with state == IDLE and (sent #-# 1) or s_nexttime state == IDLE until_with out.ready or (sent #=# 1) or (case (state) IDLE, SAMPLE: s_always [1:2] 1; default: eventually [1:2] out.valid; endcase);
    endproperty

    sent_once: assert property (counts(sent(1), 16)) else $error("count did not rise");
    assume property (@(posedge clk) stays_in_band or @(negedge clk) out.ready |-> 1);
    cover sequence (burst);
    restrict property (@(posedge clk) disable iff (!rst_n) safe);
    in_range: assert #0 (count < 16);
endmodule

(* synthesis, top = 0 *) module counter #(
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

// The datapath's checker: its count holds while a free variable, which formal tools choose, says so.
checker checker_unit(input logic clk, input logic [15:0] count, sequence settle = ##1 1'b1);
    default clocking @(posedge clk);
    endclocking

    rand bit hold;
    assert property (hold |=> $stable(count));
endchecker : checker_unit

// The watchdog, declared before its body, whose ports its declaration gives.
extern module watchdog #(
    parameter int LIMIT = 8
) (
    input logic clk,
    output logic bark
);

module watchdog (.*);
    assign bark = clk;
endmodule

// A tap on every sampler, and on its counter.
bind sampler probe_tap tap (.level());
bind sampler: u_counter watchdog #(.LIMIT(4)) dog (.clk(clk), .bark());

// A probe's halves, wired by name, and its tap.
module probe_pair (.halves({lo, hi}), .first(lo[0]), .pair(hi[1:0]), , .unused());
    input [3:0] lo, hi;
endmodule

module probe_tap (
    input .sum(probe + 1),
    .raw(probe),
    output logic level
);
    logic [3:0] probe;
endmodule

program automatic test_program (
    (* clock *) input logic clk
);
    clocking tick @(posedge clk);
    endclocking

    default clocking tick;
    event armed, fired;

    initial begin
        repeat (3) @(posedge clk);
        fork
            ##1;
        join_none
        wait fork;
        wait_order (armed, fired) $display("in order"); else $display("out of order");
        randsequence (burst)
            burst : ramp(2) steady | rand join (0.5) ramp(1) steady := 2 { $display("joined"); };
            ramp(int n = 1) : repeat (n) step | if (n > 1) step else steady | case (n) 0, 1: step; default: steady; endcase;
            step : { ##1; };
            steady : { };
            void done : { $display("done"); };
        endsequence
        ##2;
        settle: ##1 $display("time %t", $time);
        expect (@(posedge clk) ##[1:5] clk) else $display("no clock");
        @(posedge clk) assert property (@(posedge clk) clk |-> ##1 !clk);
    end
endprogram

// The testbench's transactions and drivers.
package logger_tb_pkg;
    import logger_pkg::*;
    export logger_pkg::reading_t, logger_pkg::*;
    typedef class driver;
    typedef struct {
        rand bit [7:0] gap;
        int unsigned id;
    } stimulus_t;

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
        rand byte samples[];
        local static int count = 0;
        protected int id;

        // Readings stay in the sensor's range, mostly near the cold chain's set point.
        constraint plausible {
            raw inside {[200:800]};
            soft raw dist {[300:500] :/ 8, [200:299] := 1, default :/ 1};
            samples.size() <= 8;
            foreach (samples[i])
                samples[i] > 0;
            status[2] -> {
                raw < 250;
            }
            if (status == 0)
                raw > 300;
            else if (status[7]) {
                raw < 700;
            }
            solve status before raw;
        }

        extern constraint ordered;
        pure constraint profile;

        static constraint distinct {
            unique {raw, status};
        }

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

    constraint transaction::ordered {
        disable soft raw;
    }

    class sample extends transaction #(16);
        byte history[];

        function new(int id);
            super.new(id);
            history = new[4];
        endfunction

        constraint profile {
            raw < 600;
        }

        virtual function transaction #(16) copy;
            sample other = new this;
            other.history = new[8](history);
            void'(other.randomize() with (raw) { raw > local::id; });
            return other;
        endfunction

        function int peak;
            byte high[$] = history.find(item) with (item > 8'd100);
            randcase
                3: peak = high.size();
                1: peak = std::randomize(peak) with { peak < 4; };
            endcase
        endfunction
    endclass

    // The last of the samples: no class derives from it, and it takes its base's arguments.
    class :final last_sample extends sample(default);
        ;
        local typedef byte unsigned level_t;

        virtual function :extends :final transaction #(16) copy;
            return this;
        endfunction

        constraint :extends :final profile {
            raw < 500;
        }
    endclass

    // What the testbench has seen of the readings.
    class coverage;
        transaction #(16) seen;

        covergroup readings(int unsigned limit) @(posedge seen.raw[0]);
            option.per_instance = 1;

            bit [15:0] raw_cp: coverpoint seen.raw iff (seen.status != 0) {
                bins cold[4] = {[200:399]} with (item % 2 == 0);
                bins warm[] = {[400:limit]};
                wildcard bins odd = {16'b???????????????1};
                illegal_bins hot = default;
                ignore_bins steps = (200 => 201 => 202), (300 => 301[*2:3] => 302[->1] => 303[=2]);
                bins rising = (200, 300 => 400);
                bins other = default sequence;
                bins fast = raw_cp with (item > 700);
                bins limit_bin = limit;
                option.at_least = 2;
            }

            status_cp: coverpoint seen.status;
            coverpoint seen.id;

            both: cross raw_cp, status_cp iff (limit > 0) {
                bins cold_ok = binsof(raw_cp.cold) && binsof(status_cp) intersect {[0:3]};
                ignore_bins idle = !binsof(raw_cp) || (binsof(status_cp));
                bins quiet = both with (status_cp < 2);

                function int unsigned weight;
                    return limit;
                endfunction
            }

            cross raw_cp, status_cp;
        endgroup : readings

        covergroup sampled with function sample(byte value);
            coverpoint value;
        endgroup
    endclass

    class driver;
        virtual bus_if.source bus;
        sample current = null;

        function new(virtual bus_if.source bus);
            this.bus = bus;
            current = logger_tb_pkg::sample::new(1);
        endfunction

        virtual function :initial void reset;
            current = null;
        endfunction

        extern constraint :initial settled;
    endclass
endpackage
