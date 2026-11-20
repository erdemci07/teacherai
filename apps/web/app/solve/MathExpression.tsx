'use client';
import katex from 'katex';

export function MathExpression({latex}:{latex:string}) {
  let html: string;
  try {
    html = katex.renderToString(latex,{displayMode:true,throwOnError:true});
  } catch {
    return <code className="mathError" role="note">{latex}</code>;
  }
  return <div className="boardMath" dangerouslySetInnerHTML={{__html:html}}/>;
}
