'use client';

import katex from 'katex';

type TextPart = { type: 'text'; value: string };
type MathPart = { type: 'math'; value: string; display: boolean };
type Part = TextPart | MathPart;

const RAW_COMMANDS = new Set(['frac', 'sqrt', 'sin', 'cos', 'tan', 'cot', 'log', 'ln', 'left', 'right', 'circ', 'cdot', 'times', 'rightarrow', 'Rightarrow', 'le', 'ge', 'neq', 'pm', 'pi', 'theta', 'alpha', 'beta', 'gamma', 'Delta', 'sum', 'int', 'infty']);
const RAW_COMMAND_PATTERN = /\\(frac|sqrt|sin|cos|tan|cot|log|ln|left|right|circ|cdot|times|rightarrow|Rightarrow|le|ge|neq|pm|pi|theta|alpha|beta|gamma|Delta|sum|int|infty)\b/;
const MATH_SIGNAL_PATTERN = /(\\[a-zA-Z]+|[=<>^_]|[0-9]\s*[+\-*/]|[+\-*/]\s*[0-9]|[a-zA-Z]\s*[+\-*/=^_])/;
const RAW_OPERATOR_COMMAND_PATTERN = /\\(?:times|cdot|rightarrow|Rightarrow|le|ge|neq|pm)\b/;

function normalizeLatex(value: string) {
  return value
    .trim()
    .replace(/\b(?:imes|ightarrow|Rightarrow)\b/g, (match) => (match === 'imes' ? '\\times' : `\\${match}`))
    .replace(/\\\\(?=(frac|sqrt|sin|cos|tan|cot|log|ln|left|right|circ|cdot|times|rightarrow|Rightarrow|le|ge|neq|pm|pi|theta|alpha|beta|gamma|Delta|sum|int|infty)\b)/g, '\\')
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

function commandAt(input: string, index: number) {
  if (input[index] !== '\\') return null;
  const match = /^\\([A-Za-z]+)/.exec(input.slice(index));
  return match && RAW_COMMANDS.has(match[1]) ? match[1] : null;
}

function startsMathLikeRawExpression(input: string, index: number) {
  const rest = input.slice(index);
  return (
    commandAt(input, index) ||
    scanSimpleAtom(input, index) > index ||
    /^[0-9A-Za-z]+(?:\s*\\(?:times|cdot|rightarrow|Rightarrow|le|ge|neq|pm)\b)/.test(rest)
  );
}

function readBalancedGroup(input: string, index: number) {
  if (input[index] !== '{') return index;
  let depth = 0;
  for (let i = index; i < input.length; i += 1) {
    if (input[i] === '{') depth += 1;
    if (input[i] === '}') depth -= 1;
    if (depth === 0) return i + 1;
  }
  return index;
}

function scanCommand(input: string, index: number) {
  const command = commandAt(input, index);
  if (!command) return index;
  let cursor = index + command.length + 1;
  while (input[cursor] === ' ') cursor += 1;
  if (command === 'frac') {
    const numeratorEnd = readBalancedGroup(input, cursor);
    if (numeratorEnd === cursor) return cursor;
    cursor = numeratorEnd;
    while (input[cursor] === ' ') cursor += 1;
    const denominatorEnd = readBalancedGroup(input, cursor);
    return denominatorEnd === cursor ? cursor : denominatorEnd;
  }
  if ((command === 'sqrt' || command === 'left' || command === 'right') && input[cursor] === '{') return readBalancedGroup(input, cursor);
  return cursor;
}

function scanSimpleAtom(input: string, index: number) {
  const match = /^[A-Za-z0-9]+(?:\s*(?:\^|_)\s*(?:\{[^{}]+\}|[A-Za-z0-9]+))+/.exec(input.slice(index));
  return match ? index + match[0].length : index;
}

function scanRawMath(input: string, index: number) {
  if (!startsMathLikeRawExpression(input, index)) return null;
  let cursor = index;
  let sawMath = false;

  while (cursor < input.length) {
    const commandEnd = scanCommand(input, cursor);
    if (commandEnd > cursor) {
      cursor = commandEnd; sawMath = true; continue;
    }

    const atomEnd = scanSimpleAtom(input, cursor);
    if (atomEnd > cursor) {
      cursor = atomEnd; sawMath = true; continue;
    }

    const word = /^[A-Za-z]+/.exec(input.slice(cursor));
    if (word) {
      if (word[0].length > 1) break;
      cursor += 1; continue;
    }

    const char = input[cursor];
    if (char === '\\' && RAW_OPERATOR_COMMAND_PATTERN.test(input.slice(cursor))) {
      const operator = RAW_OPERATOR_COMMAND_PATTERN.exec(input.slice(cursor));
      cursor += operator?.[0].length ?? 1; sawMath = true; continue;
    }
    if (/[0-9{}()[\]]/.test(char)) {
      cursor += 1; continue;
    }
    if (/[=<>+\-*/^_]/.test(char)) {
      cursor += 1; sawMath = true; continue;
    }
    if (/\s/.test(char)) {
      const rest = input.slice(cursor);
      if (/^\s*(?:[=<>+\-*/^_]|\\(?:frac|sqrt|sin|cos|tan|cot|log|ln|left|right|circ|cdot|times|rightarrow|Rightarrow|le|ge|neq|pm|pi|theta|alpha|beta)\b|[A-Za-z0-9]+(?:\s*(?:\^|_)))/.test(rest)) {
        cursor += 1; continue;
      }
    }
    break;
  }

  const value = normalizeLatex(input.slice(index, cursor));
  return sawMath && value ? { end: cursor, value } : null;
}

function readableMathFallback(value: string) {
  return normalizeLatex(value)
    .replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, '$1 / $2')
    .replace(/\\sqrt\{([^{}]+)\}/g, '√($1)')
    .replace(/\\(sin|cos|tan|cot|log|ln)\b/g, '$1')
    .replace(/\\rightarrow\b/g, '→')
    .replace(/\\Rightarrow\b/g, '⇒')
    .replace(/\\circ\b/g, '°')
    .replace(/\\cdot\b/g, '·')
    .replace(/\\times\b/g, '×')
    .replace(/\\le\b/g, '≤')
    .replace(/\\ge\b/g, '≥')
    .replace(/\\neq\b/g, '≠')
    .replace(/\\pm\b/g, '±')
    .replace(/\\pi\b/g, 'π')
    .replace(/\\theta\b/g, 'θ')
    .replace(/\\alpha\b/g, 'α')
    .replace(/\\beta\b/g, 'β');
}

function normalizeInlineSpacing(parts: Part[]): Part[] {
  return parts.map((part, index) => {
    if (part.type !== 'text') return part;
    let value = part.value;
    const previous = parts[index - 1];
    const next = parts[index + 1];
    if (previous?.type === 'math' && value && /^[\p{L}\p{N}\\]/u.test(value)) value = ` ${value}`;
    if (next?.type === 'math' && value && /[^\s([{"'“‘]$/u.test(value)) value = `${value} `;
    return value === part.value ? part : { ...part, value };
  });
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

    const rawMath = scanRawMath(input, index);
    if (rawMath) {
      parts.push({ type: 'math', value: rawMath.value, display: false });
      index = rawMath.end;
      continue;
    }

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

  return normalizeInlineSpacing(parts);
}

function RenderMath({ latex, display }: { latex: string; display: boolean }) {
  try {
    return (
      <span
        className={display ? 'richMath richMathDisplay' : 'richMath'}
        data-math-boundary="true"
        dangerouslySetInnerHTML={{ __html: katex.renderToString(latex, { displayMode: display, throwOnError: true }) }}
      />
    );
  } catch {
    return <code className="richMathFallback">{readableMathFallback(latex)}</code>;
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
