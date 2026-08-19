import assert from 'node:assert/strict';
import { test } from 'node:test';
import { StructuredWhiteboardRenderer } from '../src/infrastructure/rendering/whiteboard/StructuredWhiteboardRenderer.js';
import type { LessonPlan } from '../src/domain/lesson/LessonPlan.js';

test('renders structured lesson plans into whiteboard documents', async () => {
  const renderer = new StructuredWhiteboardRenderer();
  const lessonPlan: LessonPlan = {
    id: 'lesson-1',
    question: '2x = 10',
    analysis: {
      topic: 'Algebra',
      subtopic: 'Solving equations',
      difficulty: 'introductory',
      learningObjectives: [{ id: 'lo-1', description: 'Divide both sides by a coefficient.' }],
    },
    steps: [
      {
        id: 'step-1',
        title: 'Undo multiplication',
        teacherNarration: 'Divide both sides by two.',
        mathematicalStatement: '\\frac{2x}{2}=\\frac{10}{2}',
        checksForUnderstanding: ['What operation undoes multiplication by two?'],
      },
    ],
    commonMisconceptions: [],
  };

  const document = await renderer.render(lessonPlan);

  assert.equal(document.lessonPlanId, 'lesson-1');
  assert.equal(document.frames[0]?.elements[0]?.type, 'heading');
  assert.equal(document.frames[0]?.elements[1]?.type, 'math');
  assert.equal(document.frames[0]?.elements[2]?.type, 'prompt');
});
