'use client';
import katex from 'katex';
export function MathExpression({latex}:{latex:string}){try{return <div className="boardMath" dangerouslySetInnerHTML={{__html:katex.renderToString(latex,{displayMode:true,throwOnError:true})}}/>}catch{return <code className="mathError" role="note">{latex}</code>}}
