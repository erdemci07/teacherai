import { BrandMark } from './BrandMark';

export function Logo() {
  return (
    <div className="logo" aria-label="TeacherAI home">
      <BrandMark size="sm" className="logoMark" />
      <span className="logoCopy"><span className="logoText">TeacherAI</span><span className="logoTagline">Senin yapay zekâ öğretmenin</span></span>
    </div>
  );
}
