export interface AiPrompt<TInput> {
  readonly name: string;
  readonly version: string;
  readonly input: TInput;
}

export interface AiProvider<TInput, TOutput> {
  generate(prompt: AiPrompt<TInput>): Promise<TOutput>;
}
