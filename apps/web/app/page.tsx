import Link from 'next/link';

const steps = [
  'Upload a math question',
  'TeacherAI understands the topic and objective',
  'A structured lesson plan is created',
  'Renderer and voice engines prepare the learning experience',
];

const features = [
  { title: 'Teacher-quality explanations', description: 'Lessons are designed around objectives, misconceptions, and checks for understanding.' },
  { title: 'Structured LessonPlan language', description: 'AI produces reviewable JSON, while renderers and voice engines remain downstream.' },
  { title: 'Built for review', description: 'Teachers will be able to approve, correct, and improve TeacherAI outputs over time.' },
  { title: 'Scalable foundations', description: 'The platform is organized for millions of students, thousands of teachers, and replaceable AI providers.' },
];

const roadmap = ['Vision intake', 'Lesson planning', 'Whiteboard rendering', 'Voice lessons', 'Teacher review', 'Personalized learning paths'];

const faqs = [
  { question: 'Does TeacherAI solve questions directly?', answer: 'The product goal is deeper: TeacherAI creates structured lessons that teach the reasoning behind each step.' },
  { question: 'Does the AI draw on the whiteboard?', answer: 'No. AI creates LessonPlan JSON. Rendering engines convert that structure into visual learning artifacts.' },
  { question: 'Is AI implemented in Sprint 1?', answer: 'No. Sprint 1 creates the runnable web and API foundation without AI business logic.' },
];

export default function Home() {
  return (
    <>
      <section className="hero">
        <div className="heroContent">
          <p className="eyebrow">AI education platform</p>
          <h1>Teach every student like an experienced mathematics teacher.</h1>
          <p className="heroText">TeacherAI turns student questions into structured, reviewable lessons designed for whiteboards, voice, teacher feedback, and long-term learning.</p>
          <div className="heroActions">
            <Link className="primaryButton" href="/solve">Upload a question</Link>
            <Link className="secondaryButton" href="/teacher">Explore teacher tools</Link>
          </div>
        </div>
        <div className="uploadPreview" aria-label="Upload area preview">
          <div className="uploadIcon">↑</div>
          <h2>Upload Area Placeholder</h2>
          <p>Images, screenshots, and typed questions will start the TeacherAI lesson flow.</p>
          <div className="uploadLine" />
          <span>LessonPlan JSON → Renderer → Whiteboard</span>
        </div>
      </section>

      <section className="section">
        <div className="sectionHeader">
          <p className="eyebrow">How it works</p>
          <h2>From question to teachable lesson.</h2>
        </div>
        <div className="stepsGrid">
          {steps.map((step, index) => (
            <article className="stepCard" key={step}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <h3>{step}</h3>
            </article>
          ))}
        </div>
      </section>

      <section className="section altSection">
        <div className="sectionHeader">
          <p className="eyebrow">Features</p>
          <h2>Production foundations, not a demo.</h2>
        </div>
        <div className="featureGrid">
          {features.map((feature) => (
            <article className="featureCard" key={feature.title}>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section roadmapSection">
        <div className="sectionHeader">
          <p className="eyebrow">Roadmap</p>
          <h2>Designed for the full AI teacher journey.</h2>
        </div>
        <div className="roadmap">
          {roadmap.map((item) => <span key={item}>{item}</span>)}
        </div>
      </section>

      <section className="section faqSection">
        <div className="sectionHeader">
          <p className="eyebrow">FAQ</p>
          <h2>Clear boundaries from day one.</h2>
        </div>
        <div className="faqList">
          {faqs.map((faq) => (
            <article className="faqItem" key={faq.question}>
              <h3>{faq.question}</h3>
              <p>{faq.answer}</p>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
