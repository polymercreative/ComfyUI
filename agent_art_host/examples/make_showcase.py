"""Editable example sources, authored with the existing vector/paint contract."""
import json
import math
from pathlib import Path

HERE = Path(__file__).parent


def rgb(value):
    return [int(value[i:i+2], 16)/255 for i in (0, 2, 4)]


def part(name, path, color, paint=None):
    result = dict(id=name, path=path, color=rgb(color))
    if paint is not None:
        result.update(brush="pencil", paint=paint)
    return result


def point(x, y, size=4, pressure=.8, **extra):
    return dict(x=x, y=y, size=size, pressure=pressure, **extra)


def stroke(points, color, mode="cubic"):
    return dict(mode=mode, points=points, color=rgb(color))


def wash(detail=86, paper=40):
    return dict(effects=["filter/watercolor"],
        dsl=f"search filter\nread(o0).watercolor(detail: {detail}, shadowIntensity: 12, paperTexture: {paper}).write(o1)\nrender(o1)",
        output="o1", times=[0], backend="webgpu")


def document(title, description, width, height, parts, processing=None):
    result = dict(version=1, title=title, description=description, width=width, height=height, parts=parts)
    if processing:
        result["processing"] = processing
    return result


def herb():
    def stem(t):
        return 264+76*t+12*math.sin(math.pi*t), 560-412*t
    # Leaf pairs and their short petioles derive from the same stem positions.
    nodes=[(.24,[(162,389,35),(426,399,35)]),
           (.45,[(187,284,34),(440,281,33)]),
           (.66,[(225,177,31),(427,171,30)]),
           (.86,[(293,85,25),(395,75,23)])]
    sides=[]
    for side in [1,-1]:
        edge=[]
        for j in range(61):
            t=.87*j/60 if side==1 else .87*(60-j)/60
            x,y=stem(t)
            edge.append((x+side*(3.5-1.2*t),y))
        sides.extend(edge)
    stem_path='M'+' L'.join(f'{x:.2f} {y:.2f}' for x,y in sides)+' Z'
    leaves=[]
    for t,tips in nodes:
        ax,ay=stem(t)
        for ex,ey,w in tips:
            dx,dy=ex-ax,ey-ay
            length=math.hypot(dx,dy)
            ux,uy=dx/length,dy/length
            x,y=ax+ux*16,ay+uy*16
            # Extend into the blade, rather than merely touching its point.
            bx,by=x+ux*9,y+uy*9
            stem_path+=f' M{ax-uy*2:.2f} {ay+ux*2:.2f} L{bx-uy*1.5:.2f} {by+ux*1.5:.2f} L{bx+uy*1.5:.2f} {by-ux*1.5:.2f} L{ax+uy*2:.2f} {ay-ux*2:.2f} Z'
            leaves.append((x,y,ex,ey,w))
    # Union petioles with the stem so even-odd rasterization cannot cut out joints.
    from shapely.ops import unary_union
    from agent_art_host.creative.geometry import region
    polygons=[region('M'+s) for s in stem_path.split('M') if s.strip()]
    united=unary_union(polygons)
    stem_path='M'+' L'.join(f'{x:.3f} {y:.3f}' for x,y in united.exterior.coords)+' Z'
    parts=[part('stem',stem_path,'61754a',dict(size=8,spacing=3,base=.9,angle=70,variation=.045,seed=4))]
    for i, (x,y,ex,ey,w) in enumerate(leaves):
        dx,dy=ex-x,ey-y
        length=math.hypot(dx,dy)
        nx,ny=-dy/length,dx/length
        def p(t,n=0):
            return (round(x+dx*t+nx*n,2),round(y+dy*t+ny*n,2))
        def s(t,n=0):
            return " ".join(map(str,p(t,n)))
        path=f'M{x} {y} C{s(.17,w*.8)} {s(.58,w)} {s(.84,w*.46)} C{s(1.04,w*.1)} {s(1.01,-w*.16)} {s(.84,-w*.4)} C{s(.54,-w*.83)} {s(.18,-w*.65)} {x} {y} Z'
        veins=[stroke([point(*p(.05),size=2.8,out=p(.36,2)), point(*p(.92),size=1,pressure=.3,**{"in":p(.65,1)})], "c4cd91")]
        for t in [.28,.47,.66]:
            for side in [-1,1]:
                veins.append(stroke([point(*p(t),size=1.5,out=p(t+.025,side*w*.16)),
                    point(*p(t+.14,side*w*.43),size=.6,pressure=.35,**{"in":p(t+.1,side*w*.35)})],"aab77c"))
        parts.append(part(f"leaf-{i+1}",path,["657f57","7e9865","557452","91a575"][i%4],
                          dict(size=18,spacing=7,angle=math.degrees(math.atan2(dy,dx)),base=.8,
                               flow=.7,variation=.07,jitter=1.5,seed=10+i,strokes=veins)))
    parts.append(part("tie", "M269 505 Q281 510 293 506 L293 511 Q281 515 269 510 Z M270 513 Q280 518 291 514 L291 519 Q280 523 270 518 Z", "bc9155"))
    return document("Kitchen sage", "Eight independently painted leaves; seeded fills and fine spline veins.",640,640,parts,wash())


def lantern():
    parts=[]
    def add(name,path,color,paint=None): parts.append(part(name,path,color,paint))
    add("handle", "M179 207 L167 167 C149 88 184 49 250 49 C316 49 354 91 334 165 L323 207 L311 200 L322 162 C339 99 309 63 251 63 C195 63 165 97 180 161 L192 201 Z", "263f46")
    add("handle-glint", "M176 119 C177 79 209 57 250 57 L250 61 C212 64 185 83 182 121 Z", "c7b283")
    add("body-outline", "M176 229 L323 229 L351 463 Q350 494 328 503 L169 503 Q146 492 147 464 Z", "263f46")
    add("glass", "M187 237 L312 237 L335 458 Q335 478 321 484 L178 484 Q162 480 164 459 Z", "d49742",
        dict(size=38,spacing=15,angle=82,base=.95,variation=.055,seed=3))
    add("glass-lit", "M199 246 L301 246 L312 457 Q297 476 256 478 Q211 476 183 458 Z", "edbe6b",
        dict(size=30,spacing=12,angle=89,base=.93,variation=.025,seed=8))
    add("glass-shine", "M204 258 L219 258 L205 417 Q198 432 190 432 Z M226 257 L231 257 L222 323 L217 323 Z", "fae2a4")
    add("flame-outer", "M251 302 C266 340 297 351 290 391 C286 416 267 427 250 425 C218 425 203 402 213 378 C219 362 245 343 251 302 Z", "d57b32")
    add("flame", "M251 331 C250 366 280 377 273 399 C269 414 255 418 242 412 C224 403 231 386 241 374 Q252 359 251 331 Z", "ffedb4")
    add("wick", "M242 415 L260 415 L262 434 L239 434 Z", "4e5142")
    add("burner", "M219 431 Q252 423 282 431 L287 446 L215 446 Z", "866643")
    add("frame-bars", "M178 233 L192 233 L173 462 L186 485 L173 489 L158 465 Z M309 233 L322 233 L340 465 L325 491 L311 485 L326 461 Z", "344e50")
    add("bar-glints", "M180 243 L184 243 L168 457 L164 459 Z M313 243 L316 242 L333 458 L329 457 Z", "98a083")
    add("cap", "M174 204 Q249 186 326 204 L339 231 Q251 246 160 231 Z", "426261",
        dict(size=20,spacing=8,angle=10,base=.9,variation=.045,seed=25))
    add("cap-lip", "M160 228 Q250 239 339 228 L339 238 Q251 252 160 238 Z", "213d43")
    add("chimney", "M213 172 L288 172 L300 199 Q251 208 200 199 Z", "385153")
    add("vents", "M220 181 H228 V191 H220 Z M238 180 H246 V191 H238 Z M256 180 H264 V191 H256 Z M274 181 H282 V191 H274 Z", "142e37")
    add("foot", "M173 485 Q251 498 326 485 L341 513 L334 527 Q250 543 164 527 L157 513 Z", "385553",
        dict(size=18,spacing=7,angle=-5,base=.92,variation=.04,seed=30))
    add("foot-lip", "M164 519 Q249 533 334 519 L334 527 Q250 543 164 527 Z", "223e43")
    add("foot-shine", "M177 498 Q216 505 249 504 L248 509 Q213 510 174 504 Z", "a7ae8d")
    return document("Harbor lantern", "Layered vector construction, selected painted materials and separate glass, flame and metal parts.",512,600,parts)


def waves():
    bounds="M0 0 H768 V360 H0 Z"
    curves=[
        stroke([point(72,230,6,.3,out=[187,69]),point(685,174,4,.25,**{"in":[449,308]})],"819e9a"),
        stroke([point(91,252,5,.3,out=[212,85]),point(656,206,8,.3,**{"in":[424,306]})],"28616b"),
        stroke([point(115,275,3,.3,out=[233,148]),point(613,240,3,.25,**{"in":[445,313]})],"194550")]
    # The central control point creates an intentional broad pressure swell.
    curves[0]=stroke([point(72,229,5,.35),point(242,175,48,.9),point(451,219,62,.85),point(681,174,4,.3)],"819e9a","auto")
    curves[1]=stroke([point(85,254,3,.2),point(249,210,25,.9),point(437,255,39,.8),point(650,211,4,.3)],"28616b","auto")
    curves[2]=stroke([point(119,278,2,.2),point(267,246,12,.85),point(423,282,18,.8),point(604,250,2,.2)],"194550","auto")
    parts=[part("tidal-ink",bounds,"28616b",dict(fill=False,strokes=curves))]
    parts.append(part("gold-thread",bounds,"c28d40",dict(fill=False,strokes=[stroke([
        point(150,127,3,.8,out=[265,81]),point(608,120,3,.8,**{"in":[397,197]})],"c28d40")])) )
    for p in parts:
        p['brush']='wet-paint'
    return document("Tide ornament", "Four sparse splines; width and pressure interpolate along native wet-paint strokes. No silhouette fill.",768,360,parts)


def caustics():
    return document("Lagoon marbling", "Native Noisemaker noise, warp and palette: 24 frames with float master, sprite atlas and automatic motion proofs.",512,384,[],
        dict(effects=["synth/noise","filter/warp","filter/palette"],dsl="search synth, filter\nnoise(scaleX: 64, scaleY: 70, seed: 7, octaves: 2, ridges: true).warp(strength: 10, scale: 1.5, seed: 11, speed: 1).palette(index: palette.blueSkies, offset: 18).write(o1)\nrender(o1)",
             output="o1",times=[i/24 for i in range(24)],backend="webgpu"))


if __name__ == "__main__":
    for name, build in [("kitchen-sage",herb),("harbor-lantern",lantern),("tide-ornament",waves),("lagoon-light",caustics)]:
        (HERE/(name+".json")).write_text(json.dumps(build(),indent=2),encoding="utf-8")
        print(name)
