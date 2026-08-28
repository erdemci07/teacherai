type BrandMarkProps = {
  size?: 'sm' | 'md' | 'lg';
  decorative?: boolean;
  className?: string;
};

export function BrandMark({ size = 'md', decorative = true, className = '' }: BrandMarkProps) {
  const label = decorative ? undefined : 'TeacherAI eğitim simgesi';

  return (
    <span className={`brandMark brandMark-${size} ${className}`.trim()} role={decorative ? undefined : 'img'} aria-label={label}>
      <svg viewBox="0 0 48 48" aria-hidden="true" focusable="false">
        <path d="M24 9 6 17l18 8 18-8-18-8Z" />
        <path d="M13 22v8c3 4 7 6 11 6s8-2 11-6v-8l-11 5-11-5Z" />
        <path d="M39 19v10" />
        <path d="M36 31h6" />
      </svg>
    </span>
  );
}
