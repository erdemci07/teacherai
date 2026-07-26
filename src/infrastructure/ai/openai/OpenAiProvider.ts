import type { AiPrompt, AiProvider } from '../../../domain/ai/AiProvider.js';

export interface OpenAiClient {
  createStructuredCompletion<TOutput>(request: {
    readonly promptName: string;
    readonly promptVersion: string;
    readonly input: unknown;
  }): Promise<TOutput>;
}

export class OpenAiProvider<TInput, TOutput> implements AiProvider<TInput, TOutput> {
  public constructor(private readonly client: OpenAiClient) {}

  public generate(prompt: AiPrompt<TInput>): Promise<TOutput> {
    return this.client.createStructuredCompletion<TOutput>({
      promptName: prompt.name,
      promptVersion: prompt.version,
      input: prompt.input,
    });
  }
}
