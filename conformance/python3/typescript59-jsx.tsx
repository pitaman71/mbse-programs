// The conformance source for TypeScript 5.9 with JSX: JSX's kinds.
import * as React from "react";
const generic = <T,>(value: T) => value;
const element = (<div className="a" data-id={1} {...{ hidden: true }}>
        text &amp; more
        {}
        {generic("child")}
        {...[<span key="1" />]}
        <svg:path d="M0" />
        <React.Fragment>
            <>fragment</>
        </React.Fragment>
        <Component<string> prop />
    </div>);
function Component<T>(props: { prop: boolean; }) {
    return <p>{props.prop ? "yes" : "no"}</p>;
}
export default element;
