'use client';

import katex from 'katex';

type TextPart = { type: 'text'; value: string };
type MathPart = { type: 'math'; value: string; display: boolean };
type Part = TextPart | MathPart;

const RAW_COMMAND_PATTERN = /\\(frac|sqrt|cdot|times|le|ge|neq|pi|theta|alpha|beta|gamma|Delta|sum|int|infty)\b/;
const MATH_SIGNAL_PATTERN = /(\\[a-zA-Z]+|[=<>^_]|[0-9]\s*[+\-*/]|[+\-*/]\s*[0-9]|[a-zA-Z]\s*[+\-*/=^_])/;

function normalizeLatex(value: string) {
  return value
    .trim()
    .replace(/\\\\(?=(frac|sqrt|cdot|times|le|ge|neq|pi|theta|alpha|beta|gamma|Delta|sum|int|infty)\b)/g, '\\')
    .replace(/^\${1,2}\s*|\s*\${1,2}$/g, '')
    .replace(/^\\\(\s*|\s*\\\)$/g, '')
    .replace(/^\\\[\s*|\s*\\\]$/g, '')
    .trim();
}

function looksLikeMath(value: string) {
  const normalized = normalizeLatex(value);
  return RAW_COMMAND_PATTERN.test(normalized) || MATH_SIGNAL_PATTERN.test(normalized);
}

function pushText(parts: Part[], value: string) {
  if (!value) return;
  const previous = parts[parts.length - 1];
  if (previous?.type === 'text') previous.value += value;
  else parts.push({ type: 'text', value });
}

export function parseRichMathText(input: string): Part[] {
  const parts: Part[] = [];
  let index = 0;

  while (index < input.length) {
    const two = input.slice(index, index + 2);
    const one = input[index];
    let close = '';
    let end = -1;
    let display = false;
    let startOffset = 1;
    let candidateNeedsSignal = false;

    if (two === '$$') {
      close = '$$'; display = true; startOffset = 2; end = input.indexOf(close, index + startOffset);
    } else if (two === '\\(') {
      close = '\\)'; startOffset = 2; end = input.indexOf(close, index + startOffset);
    } else if (two === '\\[') {
      close = '\\]'; display = true; startOffset = 2; end = input.indexOf(close, index + startOffset);
    } else if (one === '$') {
      close = '$'; end = input.indexOf(close, index + startOffset);
    } else if (one === '(') {
      close = ')'; candidateNeedsSignal = true; end = input.indexOf(close, index + startOffset);
    } else if (one === '[') {
      close = ']'; display = true; candidateNeedsSignal = true; end = input.indexOf(close, index + startOffset);
    }

    if (end === -1 || !close) {
      pushText(parts, one);
      index += 1;
      continue;
    }

    const raw = input.slice(index + startOffset, end);
    const latex = normalizeLatex(raw);
    if (!latex || (candidateNeedsSignal && !looksLikeMath(latex))) {
      pushText(parts, input.slice(index, end + close.length));
    } else {
      parts.push({ type: 'math', value: latex, display });
    }
    index = end + close.length;
  }

  return parts;
}

function RenderMath({ latex, display }: { latex: string; display: boolean }) {
  try {
    return (
      <span
        className={display ? 'richMath richMathDisplay' : 'richMath'}
        dangerouslySetInnerHTML={{ __html: katex.renderToString(latex, { displayMode: display, throwOnError: true }) }}
      />
    );
  } catch {
    return <code className="richMathFallback">{latex}</code>;
  }
}

export function RichMathText({ text }: { text: string | null | undefined }) {
  if (!text) return null;
  return (
    <>
      {parseRichMathText(text).map((part, index) =>
        part.type === 'text' ? <span key={index}>{part.value}</span> : <RenderMath key={index} latex={part.value} display={part.display} />,
      )}
    </>
  );
}
