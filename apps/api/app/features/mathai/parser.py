import re
from sympy import Abs, Add, E, Eq, Float, Integer, Mul, Pow, Rational, Symbol, pi, sqrt
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application, convert_xor
class MathParseError(ValueError): pass
_ALLOWED=re.compile(r"^[0-9A-Za-z_+\-*/^().,= |{}\\]+$")
_TRANS=standard_transformations+(implicit_multiplication_application,convert_xor)
_GLOBAL={"Symbol":Symbol,"Integer":Integer,"Float":Float,"Rational":Rational,"Add":Add,"Mul":Mul,"Pow":Pow,"Abs":Abs,"sqrt":sqrt,"pi":pi,"E":E}
def normalize(value:str)->str:
    text=value.strip().replace("$","").replace("\\left","").replace("\\right","").replace("\\cdot","*").replace("\\times","*").replace("\\pm","+")
    text=text.replace("\\,","").replace("−","-").replace("÷","/")
    for _ in range(5):
        changed=re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}",r"(\1)/(\2)",text)
        if changed==text: break
        text=changed
    text=re.sub(r"\\sqrt\{([^{}]+)\}",r"sqrt(\1)",text)
    text=re.sub(r"\|([^|]+)\|",r"Abs(\1)",text)
    text=text.replace("{","(").replace("}",")")
    return text
def expression(value:str):
    text=normalize(value)
    if len(text)>500 or not _ALLOWED.fullmatch(value.strip()): raise MathParseError("unsupported characters")
    if "__" in text: raise MathParseError("invalid identifier")
    names=set(re.findall(r"[A-Za-z_]+",text)); allowed_functions={"Abs","sqrt"}
    variables=names-allowed_functions
    if len(variables)>6: raise MathParseError("too many variables")
    local={name:Symbol(name,real=True) for name in variables}|{"Abs":Abs,"sqrt":sqrt}
    try: return parse_expr(text,local_dict=local,global_dict=_GLOBAL,transformations=_TRANS,evaluate=False)
    except Exception as exc: raise MathParseError("cannot parse expression") from exc
def equation(value:str):
    text=normalize(value)
    if text.count("=")!=1: raise MathParseError("not an equation")
    left,right=text.split("=",1)
    return Eq(expression(left),expression(right),evaluate=False)
