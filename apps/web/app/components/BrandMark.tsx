type BrandMarkProps = {
  size?: 'sm' | 'md' | 'lg';
  decorative?: boolean;
  className?: string;
};

export function BrandMark({ size = 'md', decorative = true, className = '' }: BrandMarkProps) {
  const label = decorative ? undefined : 'TeacherAI maskotu';

  return (
    <span className={`brandMark brandMark-${size} ${className}`.trim()}>
      <img src="/teacherai-mascot.png" alt={label ?? ''} aria-hidden={decorative} />
    </span>
  );
}
