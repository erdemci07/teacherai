import { VisionAnalysis } from '../lib/vision-api';

const difficultyLabels = { easy: 'Kolay', medium: 'Orta', hard: 'Zor', unknown: 'Belirlenemedi' };

export function AnalysisResult({ result }: { result: VisionAnalysis }) {
  const visualLabels = [
    result.visual_elements.has_diagram && 'Şema',
    result.visual_elements.has_graph && 'Grafik',
    result.visual_elements.has_table && 'Tablo',
    result.visual_elements.has_geometry_figure && 'Geometri şekli',
  ].filter(Boolean);

  return (
    <section className="analysisResult" aria-labelledby="analysis-title">
      <div className="resultSuccess" role="status">✓ Soru başarıyla okundu.</div>
      <div className="resultHeading">
        <div><p className="eyebrow">Soru analizi</p><h2 id="analysis-title">{result.topic}</h2></div>
        <div className="confidence"><strong>%{Math.round(result.confidence * 100)}</strong><span>güven</span></div>
      </div>
      <div className="resultTags">
        {result.exam_context && <span>{result.exam_context}</span>}
        <span>{result.subtopic ?? result.question_type}</span>
        <span>{difficultyLabels[result.difficulty]}</span>
      </div>
      <div className="resultBlock"><h3>Okunan soru</h3><p>{result.question_text}</p></div>
      {result.mathematical_expressions.length > 0 && (
        <div className="resultBlock"><h3>Matematiksel ifadeler</h3><div className="formulaList">{result.mathematical_expressions.map((item) => <code key={item}>{item}</code>)}</div></div>
      )}
      <div className="resultBlock">
        <h3>Görsel bağlam</h3>
        <p>{result.visual_elements.description ?? (visualLabels.length ? visualLabels.join(', ') : 'Ek bir görsel öğe algılanmadı.')}</p>
      </div>
      {result.ocr_uncertainties.length > 0 && <div className="uncertainty"><strong>Kontrol edilecek alanlar</strong><ul>{result.ocr_uncertainties.map((item) => <li key={item}>{item}</li>)}</ul></div>}
      <button type="button" className="primaryButton resultCta" disabled>Öğretmen Gibi Anlat · Sprint 3</button>
      {result.debug && <details className="technicalDetails"><summary>Teknik Detaylar</summary><pre>{JSON.stringify(result.debug, null, 2)}</pre></details>}
    </section>
  );
}
