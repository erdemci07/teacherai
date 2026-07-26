import assert from 'node:assert/strict';
import { test } from 'node:test';
import { CreateTeachableLesson } from '../src/application/lesson-planning/CreateTeachableLesson.js';
import type { LessonPlan, QuestionAnalysis } from '../src/domain/lesson/LessonPlan.js';

test('creates a lesson plan from analysis without coupling to renderers or providers', async () => {
  const analysis: QuestionAnalysis = {
    topic: 'Algebra',
    subtopic: 'Linear equations',
    difficulty: 'developing',
    learningObjectives: [{ id: 'lo-1', description: 'Solve one-step linear equations.' }],
  };

  const lessonPlan: LessonPlan = {
    id: 'lesson-1',
    question: 'x + 3 = 7',
    analysis,
    steps: [
      {
        id: 'step-1',
        title: 'Isolate the variable',
        teacherNarration: 'Subtract three from both sides to keep the equation balanced.',
        mathematicalStatement: 'x + 3 - 3 = 7 - 3',
        checksForUnderstanding: ['Why do we subtract three from both sides?'],
      },
    ],
    commonMisconceptions: ['Changing only one side of the equation.'],
  };

  const useCase = new CreateTeachableLesson(
    { analyze: async () => analysis },
    { createLessonPlan: async () => lessonPlan },
  );

  const result = await useCase.execute({ question: 'x + 3 = 7' });

  assert.deepEqual(result, lessonPlan);
});
