'use client';

// TA-003: Son çare netleştirme. Yalnızca otomatik denetimler ve tek hedefli yeniden okuma
// sonuca bağlı bir belirsizliği çözemediyse gösterilir.

import type { ClarificationOption, QuestionState } from '../lib/clarification.ts';
import { MathExpression } from './MathExpression.tsx';

type Props = {
  state: Exclude<QuestionState, { kind: 'proceed' }>;
  pending: boolean;
  onSelect: (uncertaintyId: string, selection: string) => void;
  onRetake: () => void;
  onReplace: () => void;
};

function OptionContent({ option }: { option: ClarificationOption }) {
  return option.latex ? <MathExpression latex={option.latex} /> : <span>{option.text}</span>;
}

export function ClarificationPanel({ state, pending, onSelect, onRetake, onReplace }: Props) {
  if (state.kind !== 'clarify') {
    return <section className="clarificationPanel" aria-live="polite">
      <p>{state.message}</p>
      {state.kind !== 'unsupported' && <div className="invalidImageActions">
        <button type="button" className="primaryButton" onClick={onRetake}>📷 Tekrar Çek</button>
        <button type="button" className="secondaryButton" onClick={onReplace}>Başka Görsel Seç</button>
      </div>}
    </section>;
  }
  const { uncertainty, prompt, options } = state;
  return <section className="clarificationPanel" aria-live="polite">
    <fieldset disabled={pending}>
      <legend>{prompt}</legend>
      <div className="clarificationOptions">
        {options.map((option, index) => <button key={option.id} type="button" className="secondaryButton"
          onClick={() => onSelect(uncertainty.id, option.id)}
          aria-label={`${index === 0 ? 'İlk okuduğum' : 'Diğer olasılık'}: ${option.text}`}>
          <OptionContent option={option} />
        </button>)}
      </div>
      <div className="invalidImageActions">
        <button type="button" className="secondaryButton" onClick={() => onSelect(uncertainty.id, 'none')}>Hiçbiri doğru değil</button>
        <button type="button" className="secondaryButton" onClick={onRetake}>📷 Daha net çek</button>
      </div>
    </fieldset>
    {pending && <p role="status">Seçimini kaydediyorum…</p>}
  </section>;
}
