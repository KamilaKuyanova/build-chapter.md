// 3D презентации без библиотек: фон из структурных изолиний и блок, который из стопки страниц становится слоями породы.
const GLX = (() => {
  const cv = document.getElementById('gl'), gl = cv.getContext('webgl2', { antialias: true, alpha: true, premultipliedAlpha: false, preserveDrawingBuffer: true });
  if (!gl) return { ok: false, S: {}, T: {}, frame() {}, project() { return [0, 0]; } };
  const sh = (t, s) => { const o = gl.createShader(t); gl.shaderSource(o, s); gl.compileShader(o); if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) console.error(gl.getShaderInfoLog(o), s.split('\n').slice(0, 3)); return o; };
  const prog = (v, f) => { const p = gl.createProgram(); gl.attachShader(p, sh(gl.VERTEX_SHADER, v)); gl.attachShader(p, sh(gl.FRAGMENT_SHADER, f)); gl.bindAttribLocation(p, 0, 'a'); gl.linkProgram(p); if (!gl.getProgramParameter(p, gl.LINK_STATUS)) console.error(gl.getProgramInfoLog(p)); const u = {}; for (let i = 0; i < gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS); i++) { const n = gl.getActiveUniform(p, i).name; u[n] = gl.getUniformLocation(p, n); } return { p, u }; };
  const NOISE = `
float h21(vec2 p){p=fract(p*vec2(123.34,456.21));p+=dot(p,p+45.32);return fract(p.x*p.y);}
float vn(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*f*(f*(f*6.-15.)+10.);return mix(mix(h21(i),h21(i+vec2(1,0)),f.x),mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),f.x),f.y);}
float fbm(vec2 p){float a=.5,s=0.;for(int i=0;i<4;i++){s+=a*vn(p);p=p*2.03+7.1;a*=.5;}return s;}`;
  // ---------- фон
  const bg = prog(`#version 300 es
in vec2 a;out vec2 v;void main(){v=a;gl_Position=vec4(a,0.9999,1);}`, `#version 300 es
precision highp float;in vec2 v;out vec4 o;uniform float t,light,contour,deep;uniform vec2 res,mouse;${NOISE}
float field(vec2 p){vec2 q=p*.62+vec2(t*.008,-t*.005);q+=.55*vec2(vn(q*.9+3.),vn(q*.9+9.));return vn(q*.95)*.72+vn(q*1.9+4.)*.22;}
float tube(float h){float f=abs(fract(h*12.)-.5)*2.;return smoothstep(.62,.12,f);}
void main(){
 vec2 uv=v*.5+.5;float asp=res.x/res.y;vec2 p=vec2((uv.x-.5)*asp,uv.y-.5)*3.2+mouse*.06;
 float y=1.-uv.y;
 vec3 k0=vec3(.004,.008,.016),k1=vec3(.012,.055,.150),k2=vec3(.035,.205,.485),k3=vec3(.28,.47,.70);
 float g=y+(.16*length(vec2(uv.x-.5,0.))-.04);
 vec3 c=mix(k0,k1,smoothstep(.02,.42,g));c=mix(c,k2,smoothstep(.36,.80,g)*(1.-deep));c=mix(c,k3,smoothstep(.80,1.12,g)*(1.-deep)*.85);
 vec3 lc=mix(vec3(.965,.967,.960),vec3(.735,.815,.895),smoothstep(.55,1.15,uv.y+.25*abs(uv.x-.5)));
 c=mix(c,lc,light);
 if(contour>.01){
  float h=field(p),e=.012;float hx=field(p+vec2(e,0)),hy=field(p+vec2(0,e));
  float T=tube(h),Tx=tube(hx),Ty=tube(hy);vec2 n=vec2(Tx-T,Ty-T)/e*.034;
  float d=dot(normalize(vec3(-n,1.)),normalize(vec3(-.5,.75,.55)));
  float rel=(d-.52);
  float vig=smoothstep(.15,.85,length((uv-vec2(.5,.52))*vec2(1.15,1.)));
  vec3 hi=mix(vec3(.55,.72,.95),vec3(1.),.3),lo=vec3(0.);
  c+=contour*(rel>0.?hi*rel*.52:lo)*mix(.35,1.,vig)*(1.-light*.8);
  c*=1.+contour*min(rel,0.)*.75*mix(.5,1.,vig)*(1.-light*.86);
 }
 o=vec4(c,1.);
}`);
  // фон мягкий, поэтому считается в половинном размере через кадр и растягивается
  const cp = prog(`#version 300 es
in vec2 a;out vec2 v;void main(){v=a*.5+.5;gl_Position=vec4(a,0.9999,1);}`, `#version 300 es
precision highp float;in vec2 v;out vec4 o;uniform sampler2D tx;uniform float t;float h(vec2 p){p=fract(p*vec2(123.34,456.21));p+=dot(p,p+45.32);return fract(p.x*p.y);}void main(){o=vec4(texture(tx,v).rgb+(h(gl_FragCoord.xy+fract(t))-.5)*.014,1.);}`);
  const tex = gl.createTexture(), fbo = gl.createFramebuffer(); let bw = 0, bh = 0, fr = 0;
  const bgSize = (w, h) => { if (w === bw && h === bh) return; bw = w; bh = h; gl.bindTexture(gl.TEXTURE_2D, tex); gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null); for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v); gl.bindFramebuffer(gl.FRAMEBUFFER, fbo); gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0); gl.bindFramebuffer(gl.FRAMEBUFFER, null); fr = 0; };
  const quad = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, quad); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const bgV = gl.createVertexArray(); gl.bindVertexArray(bgV); gl.enableVertexAttribArray(gl.getAttribLocation(bg.p, 'a')); gl.vertexAttribPointer(gl.getAttribLocation(bg.p, 'a'), 2, gl.FLOAT, false, 0, 0);
  // ---------- блок: поверхности слоёв считаются в вершинном шейдере
  const SURF = `
uniform float fold,explode,lift,layer;uniform mat4 M,P;
const float B[7]=float[7](-.92,-.60,-.30,.06,.30,.56,.80);const float A[7]=float[7](.46,.50,.50,.50,.42,.16,.02);
float surf(int k,vec2 q){float a=exp(-q.x*q.x*.95-q.y*q.y*.07)-.36;float s=A[k]*a*1.15+.03*sin(q.x*2.6+float(k))*A[k]*2.+.02*sin(q.y*3.1+float(k)*2.);
 float flat_=-.66+float(k)*.235;return mix(flat_,B[k]+s,fold);}
float yAt(vec2 q,float tt){int k=int(layer);return mix(surf(k,q),surf(k+1,q),tt);}
float off(){return (layer-2.5)*explode*.43+lift;}`;
  const solid = prog(`#version 300 es
in vec4 a;in vec3 nrm;out vec3 vP,vN,vO;out float vT;flat out int vF;${SURF}
void main(){vec2 q=a.xy;float y=yAt(q,a.z);vec3 o=vec3(q.x,y,q.y);vec3 n=nrm;
 if(a.w<1.5){float e=.02;n=normalize(vec3(-(yAt(q+vec2(e,0),a.z)-y)/e,1.,-(yAt(q+vec2(0,e),a.z)-y)/e));if(a.w<.5)n=-n;}
 vO=o;vT=a.z;vF=int(a.w+.5);vec4 w=M*vec4(o.x,o.y+off(),o.z,1.);vP=w.xyz;vN=mat3(M)*n;gl_Position=P*w;}`, `#version 300 es
precision highp float;in vec3 vP,vN,vO;in float vT;flat in int vF;out vec4 o;
uniform float fold,layer,t,light,wire,wipe,glow,alpha,fluid;uniform vec2 res;${NOISE}
vec3 env(vec3 r){float u=r.y*.5+.5;vec3 c=mix(vec3(.02,.03,.05),vec3(.20,.33,.55),smoothstep(.2,.62,u));c=mix(c,vec3(.95,.97,1.),smoothstep(.70,.93,u));c+=vec3(.75,.85,1.)*smoothstep(.93,.99,sin(r.x*3.+1.2)*.5+.5)*.35;return c;}
void main(){
 vec3 N=normalize(vN),V=normalize(-vP);if(dot(N,V)<0.)N=-N;
 int L=int(layer);bool side=vF>=2;vec2 q=side?vec2((vF<4)?vO.z:vO.x,vO.y):vO.xz;
 // бумага
 vec3 pap=vec3(.90,.90,.885);
 if(side){float s=vT*46.+.35*vn(vec2(q.x*5.,layer));pap*=.74+.26*smoothstep(.15,.6,abs(fract(s)-.5)*2.);pap*=.9+.1*vn(vec2(q.x*60.,s*2.));}
 else if(vF==1){vec2 m=vO.xz;float row=floor((m.y+1.02)*13.),f=fract((m.y+1.02)*13.);float w=1.08-step(.8,h21(vec2(row,layer+3.)))*(.5+.6*h21(vec2(row,2.)));float line=smoothstep(.36,.42,f)*smoothstep(.66,.60,f)*step(-1.18,m.x)*step(m.x,w)*step(-.96,m.y)*step(m.y,.92);
  float word=step(.16,fract(m.x*(5.+2.*h21(vec2(row,9.)))+h21(vec2(row,1.))*3.+.3*sin(m.x*9.+row)));float head=step(row,1.5);pap=mix(pap,vec3(.10,.13,.18),line*word*mix(.62,.92,head)*step(m.x,head>.5?.3:2.));}
 // порода
 float g=vn(q*34.)*.5+vn(q*80.)*.5;vec3 c=vec3(.5);float rough=.6,met=.0;
 if(L==0){c=vec3(.15,.165,.19);c+=.07*smoothstep(.55,.75,fbm(q*5.+vec2(0,vT*2.)));c*=.75+.5*g;rough=.45;}
 else if(L==1){c=vec3(.52,.56,.60);float ro=floor(vT*5.);float br=side?min(smoothstep(.0,.07,fract(vT*5.)),smoothstep(.0,.03,fract(q.x*1.4+mod(ro,2.)*.5))):1.;c*=(.80+.2*br)*(.86+.22*g);rough=.5;}
 else if(L==2){c=vec3(.70,.69,.65)*(.72+.5*g);if(fluid>.01&&side){float y=vO.y+.012*sin(q.x*3.+t*.6);vec3 fl=y>.205?vec3(.86,.27,.22):(y>.035?vec3(.14,.50,.32):vec3(.16,.44,.78));c=mix(c,fl*(.62+.65*g),.82*fluid);c+=fluid*.9*(smoothstep(.010,.0,abs(y-.205))+smoothstep(.010,.0,abs(y-.035)))*vec3(.9);}rough=.6;}
 else if(L==3){c=vec3(.80,.85,.90)*(.90+.14*vn(q*7.));rough=.12;met=.55;}
 else if(L==4){float s=vT*9.+.6*vn(q*3.);c=mix(vec3(.30,.36,.43),vec3(.44,.50,.56),smoothstep(.3,.7,fract(s)))*(.84+.26*g);rough=.5;}
 else{float s=vT*16.+.5*vn(vec2(q.x*3.,vT*4.));c=mix(vec3(.17,.21,.26),vec3(.27,.32,.38),smoothstep(.2,.8,fract(s)))*(.82+.3*g);rough=.55;if(vF==1){c=vec3(.30,.35,.40)*(.7+.5*fbm(q*4.));}}
 float f=smoothstep(.15,.85,fold);c=mix(pap,c,f);rough=mix(.85,rough,f);met*=f;
 vec3 K=normalize(vec3(-.45,.9,.55)),R=reflect(-V,N);
 float df=max(dot(N,K),0.),fr=pow(1.-max(dot(N,V),0.),4.);
 float sp=pow(max(dot(R,K),0.),mix(90.,8.,rough))*mix(.9,.10,rough);
 float fill=max(dot(N,normalize(vec3(.25,.12,1.))),0.);vec3 amb=mix(vec3(.17,.22,.30),vec3(.46,.49,.54),light)*(.7+.3*N.y)+vec3(.52,.54,.58)*fill;
 vec3 col=c*(amb+df*.78)+sp;col=mix(col,env(R)*mix(vec3(1.),c,.35),met*.75);
 col+=fr*mix(vec3(.18,.40,.85),vec3(.45,.58,.75),light)*.42;
 float edge=side?smoothstep(.0,.05,vT)*smoothstep(1.,.95,vT):1.;col*=mix(.72,1.,edge);
 col+=glow*vec3(.05,.28,.95)*.55;
 float yy=gl_FragCoord.y/res.y;float w=wire*step(yy,wipe);
 col=mix(col,vec3(.018,.020,.026),w);
 o=vec4(pow(col,vec3(.92)),alpha);
}`);
  const X = 1.42, Z = 1.02, NX = 36, NZ = 26, verts = [], idx = [];
  const grid = (nu, nv, fn) => { const s = verts.length / 7; for (let j = 0; j <= nv; j++) for (let i = 0; i <= nu; i++) verts.push(...fn(i / nu, j / nv)); for (let j = 0; j < nv; j++) for (let i = 0; i < nu; i++) { const k = s + j * (nu + 1) + i; idx.push(k, k + 1, k + nu + 1, k + 1, k + nu + 2, k + nu + 1); } };
  for (const top of [1, 0]) grid(NX, NZ, (u, v) => [(u * 2 - 1) * X, (v * 2 - 1) * Z, top, top, 0, top ? 1 : -1, 0]);
  grid(NZ, 6, (u, v) => [X, (u * 2 - 1) * Z, v, 2, 1, 0, 0]); grid(NZ, 6, (u, v) => [-X, (u * 2 - 1) * Z, v, 3, -1, 0, 0]);
  grid(NX, 6, (u, v) => [(u * 2 - 1) * X, Z, v, 4, 0, 0, 1]); grid(NX, 6, (u, v) => [(u * 2 - 1) * X, -Z, v, 5, 0, 0, -1]);
  const vb = (data) => { const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.STATIC_DRAW); return b; };
  const solidV = gl.createVertexArray(); gl.bindVertexArray(solidV); vb(verts);
  const at = (p, n, s, st, of) => { const l = gl.getAttribLocation(p, n); if (l < 0) return; gl.enableVertexAttribArray(l); gl.vertexAttribPointer(l, s, gl.FLOAT, false, st * 4, of * 4); };
  at(solid.p, 'a', 4, 7, 0); at(solid.p, 'nrm', 3, 7, 4);
  const ib = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint32Array(idx), gl.STATIC_DRAW);
  // ---------- пунктирные рёбра
  const line = prog(`#version 300 es
in vec4 a;out float vD;${SURF}
void main(){vec2 q=a.xy;vec4 w=M*vec4(q.x,yAt(q,a.z)+off(),q.y,1.);vD=a.w;gl_Position=P*w;gl_Position.z-=.0004*gl_Position.w;}`, `#version 300 es
precision highp float;in float vD;out vec4 o;uniform float alpha,dash,wipe,wire;uniform vec3 col;uniform vec2 res;
void main(){if(dash>.5&&fract(vD*15.)>.55)discard;if(wire>.5&&gl_FragCoord.y/res.y>wipe)discard;o=vec4(col,alpha);}`);
  const seg = [], inner = [];
  const pathTo = (out, pts) => { let d = 0; for (let i = 1; i < pts.length; i++) { const p = pts[i - 1], r = pts[i], l = Math.hypot(r[0] - p[0], r[1] - p[1], (r[2] - p[2]) * .25); out.push(...p, d, ...r, d + l); d += l; } };
  const N = 30, lin = (f) => Array.from({ length: N + 1 }, (_, i) => f(i / N * 2 - 1));
  for (const top of [0, 1]) { pathTo(seg, lin(u => [u * X, Z, top])); pathTo(seg, lin(u => [u * X, -Z, top])); pathTo(seg, lin(u => [X, u * Z, top])); pathTo(seg, lin(u => [-X, u * Z, top])); }
  for (const x of [-X, X]) for (const z of [-Z, Z]) pathTo(seg, [[x, z, 0], [x, z, 1]]);
  for (let i = 1; i < 10; i++) pathTo(inner, lin(u => [u * X, (i / 10 * 2 - 1) * Z, 1]));
  for (let i = 1; i < 14; i++) pathTo(inner, lin(u => [(i / 14 * 2 - 1) * X, u * Z, 1]));
  const lineV = gl.createVertexArray(); gl.bindVertexArray(lineV); vb(seg.concat(inner)); at(line.p, 'a', 4, 4, 0);
  const nSeg = seg.length / 4, nInner = inner.length / 4;
  // ---------- скважина и пыль
  const tube = prog(`#version 300 es
in vec3 a;out vec3 vN,vP;out float vY;uniform mat4 M,P;uniform float y0,y1,rad;uniform vec2 at;
void main(){vec3 p=vec3(at.x+a.x*rad,mix(y0,y1,a.y),at.y+a.z*rad);vY=p.y;vN=mat3(M)*vec3(a.x,0,a.z);vec4 w=M*vec4(p,1);vP=w.xyz;gl_Position=P*w;}`, `#version 300 es
precision highp float;in vec3 vN,vP;in float vY;out vec4 o;uniform float alpha,t;
void main(){vec3 N=normalize(vN),V=normalize(-vP);float k=dot(N,normalize(vec3(-.6,.3,.7)));float s=smoothstep(.2,.9,k);vec3 c=mix(vec3(.10,.12,.15),vec3(.93,.95,.98),s*s);c+=.35*pow(max(k,0.),18.);c*=.86+.14*step(.12,fract(vY*3.));o=vec4(c,alpha);}`);
  const tv = []; for (let i = 0; i < 24; i++) { const p = k => [Math.cos(k / 24 * 6.2832), Math.sin(k / 24 * 6.2832)]; const A0 = p(i), A1 = p(i + 1); tv.push(A0[0], 0, A0[1], A1[0], 0, A1[1], A0[0], 1, A0[1], A1[0], 0, A1[1], A1[0], 1, A1[1], A0[0], 1, A0[1]); }
  const tubeV = gl.createVertexArray(); gl.bindVertexArray(tubeV); vb(tv); at(tube.p, 'a', 3, 3, 0);
  const dust = prog(`#version 300 es
in vec4 a;out float vA;uniform mat4 P;uniform float t,dpr;void main(){vec3 p=a.xyz*vec3(5.2,3.,2.4);p.y=mod(p.y+t*.05*(.4+a.w)+3.,6.)-3.;p.x+=.12*sin(t*.3+a.w*9.);p.z-=6.2;gl_Position=P*vec4(p,1);gl_PointSize=dpr*(1.+2.6*a.w)*(6./-p.z);vA=.18+.5*a.w*(.5+.5*sin(t+a.w*40.));}`, `#version 300 es
precision highp float;in float vA;out vec4 o;uniform float alpha;void main(){float d=length(gl_PointCoord-.5);o=vec4(.72,.84,1.,smoothstep(.5,.1,d)*vA*alpha);}`);
  const dv = []; for (let i = 0; i < 150; i++) dv.push(Math.random() * 2 - 1, Math.random() * 2 - 1, Math.random() * 2 - 1, Math.random());
  const dustV = gl.createVertexArray(); gl.bindVertexArray(dustV); vb(dv); at(dust.p, 'a', 4, 4, 0);
  // ---------- матрицы
  const mul = (a, b) => { const o = new Float32Array(16); for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) { let s = 0; for (let k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k]; o[c * 4 + r] = s; } return o; };
  const persp = (f, asp, n, z) => new Float32Array([f / asp, 0, 0, 0, 0, f, 0, 0, 0, 0, (z + n) / (n - z), -1, 0, 0, 2 * z * n / (n - z), 0]);
  const T = { x: 0, y: 0, z: -7.2, rx: .42, ry: -.6, rz: 0, scale: 1, fold: 0, explode: 0, light: 0, contour: 1, deep: 0, wire: 0, wipe: 1, show: 1, lines: 0, well: 0, dust: 1, fluid: 1, spin: 1, hot: -1, depth: 1.6 };
  const S = { ...T }, mouse = [0, 0], ms = [0, 0];
  addEventListener('pointermove', e => { mouse[0] = e.clientX / innerWidth * 2 - 1; mouse[1] = e.clientY / innerHeight * 2 - 1; });
  let Mx, Pm, dpr = Math.min(devicePixelRatio || 1, 1.25), slow = 0;
  const size = () => { const w = Math.round(innerWidth * dpr), h = Math.round(innerHeight * dpr); if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; } };
  const hotL = [0, 0, 0, 0, 0, 0];
  let last = 0, spin = 0;
  function frame(now) {
    const t = now / 1000, dt = Math.min(.05, t - last || .016); last = t;
    if (dt > .038) { if (++slow > 70 && dpr > .8) { dpr *= .8; slow = 0; } } else slow = Math.max(0, slow - 1);
    for (const k in T) { if (k === 'hot') { S.hot = T.hot; continue; } const r = k === 'fold' || k === 'explode' ? 2.6 : k === 'wipe' ? 1.6 : 3.6; S[k] += (T[k] - S[k]) * (1 - Math.exp(-r * dt)); }
    ms[0] += (mouse[0] - ms[0]) * .06; ms[1] += (mouse[1] - ms[1]) * .06;
    spin += dt * .12 * S.spin;
    size();
    const W = cv.width, H = cv.height;
    gl.viewport(0, 0, W, H); gl.disable(gl.BLEND); gl.disable(gl.DEPTH_TEST); gl.clearColor(0, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.useProgram(bg.p); gl.bindVertexArray(bgV); gl.uniform1f(bg.u.t, t); gl.uniform1f(bg.u.light, S.light); gl.uniform1f(bg.u.contour, S.contour); gl.uniform1f(bg.u.deep, S.deep); gl.uniform2f(bg.u.res, W, H); gl.uniform2f(bg.u.mouse, ms[0], -ms[1]);
    bgSize(Math.max(2, Math.round(Math.min(W, 1700) * .5)), Math.max(2, Math.round(Math.min(W, 1700) * .5 * H / W)));
    if (fr++ % 2 === 0) { gl.bindFramebuffer(gl.FRAMEBUFFER, fbo); gl.viewport(0, 0, bw, bh); gl.drawArrays(gl.TRIANGLES, 0, 3); gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.viewport(0, 0, W, H); }
    gl.useProgram(cp.p); gl.bindTexture(gl.TEXTURE_2D, tex); gl.uniform1f(cp.u.t, t); gl.drawArrays(gl.TRIANGLES, 0, 3);
    Pm = persp(3.6 * Math.min(1, W / H / (16 / 9)), W / H, .1, 40);
    const ry = S.ry + Math.sin(spin) * .42 * S.spin + ms[0] * .12, rx = S.rx + ms[1] * .06, cy = Math.cos(ry), sy = Math.sin(ry), cx = Math.cos(rx), sx = Math.sin(rx), cz = Math.cos(S.rz), sz = Math.sin(S.rz), k = S.scale;
    const Ry = new Float32Array([cy, 0, -sy, 0, 0, 1, 0, 0, sy, 0, cy, 0, 0, 0, 0, 1]), Rx = new Float32Array([1, 0, 0, 0, 0, cx, sx, 0, 0, -sx, cx, 0, 0, 0, 0, 1]), Rz = new Float32Array([cz, sz, 0, 0, -sz, cz, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);
    const Tr = new Float32Array([k, 0, 0, 0, 0, k, 0, 0, 0, 0, k, 0, S.x, S.y, S.z, 1]);
    Mx = mul(Tr, mul(Rz, mul(Rx, Ry)));
    gl.enable(gl.BLEND); gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    if (S.dust > .02) { gl.useProgram(dust.p); gl.bindVertexArray(dustV); gl.uniformMatrix4fv(dust.u.P, false, Pm); gl.uniform1f(dust.u.t, t); gl.uniform1f(dust.u.dpr, dpr); gl.uniform1f(dust.u.alpha, S.dust * (1 - S.light)); gl.drawArrays(gl.POINTS, 0, 150); }
    if (S.show < .02) return;
    gl.enable(gl.DEPTH_TEST);
    gl.useProgram(solid.p); gl.bindVertexArray(solidV);
    const U = solid.u; gl.uniformMatrix4fv(U.M, false, Mx); gl.uniformMatrix4fv(U.P, false, Pm); gl.uniform2f(U.res, W, H);
    for (const n of ['fold', 'explode', 'light', 'wire', 'wipe', 'fluid']) if (U[n]) gl.uniform1f(U[n], S[n]);
    gl.uniform1f(U.t, t); gl.uniform1f(U.alpha, S.show);
    for (let i = 0; i < 6; i++) { hotL[i] += ((T.hot === i ? 1 : 0) - hotL[i]) * .12; gl.uniform1f(U.layer, i); gl.uniform1f(U.glow, hotL[i] * .35); gl.uniform1f(U.lift, Math.sin(t * .9 + i * .7) * .012 * S.explode); gl.drawElements(gl.TRIANGLES, idx.length, gl.UNSIGNED_INT, 0); }
    if (S.well > .02) { gl.useProgram(tube.p); gl.bindVertexArray(tubeV); gl.uniformMatrix4fv(tube.u.M, false, Mx); gl.uniformMatrix4fv(tube.u.P, false, Pm); gl.uniform1f(tube.u.alpha, S.well * S.show); gl.uniform2f(tube.u.at, .0, Z + .02); for (const [r, a, b] of [[.030, 1.45, 1.45 - S.depth * S.well], [.052, 1.45, 1.45 - .72 * S.well]]) { gl.uniform1f(tube.u.rad, r); gl.uniform1f(tube.u.y0, b); gl.uniform1f(tube.u.y1, a); gl.drawArrays(gl.TRIANGLES, 0, tv.length / 3); } }
    const la = Math.max(S.lines, S.wire);
    if (la > .02) {
      gl.useProgram(line.p); gl.bindVertexArray(lineV); const u = line.u; gl.uniformMatrix4fv(u.M, false, Mx); gl.uniformMatrix4fv(u.P, false, Pm); gl.uniform1f(u.fold, S.fold); gl.uniform1f(u.explode, S.explode); gl.uniform2f(u.res, W, H); gl.uniform1f(u.wipe, S.wipe); gl.uniform1f(u.wire, S.wire > .5 ? 1 : 0); gl.uniform1f(u.dash, 1);
      for (let i = 0; i < 6; i++) { gl.uniform1f(u.layer, i); gl.uniform1f(u.lift, Math.sin(t * .9 + i * .7) * .012 * S.explode); gl.uniform3f(u.col, .86, .92, 1); gl.uniform1f(u.alpha, la * .62); gl.drawArrays(gl.LINES, 0, nSeg); if (S.wire > .3 && i === 5) { gl.uniform1f(u.alpha, .22 * S.wire); gl.drawArrays(gl.LINES, nSeg, nInner); } }
    }
    gl.disable(gl.DEPTH_TEST);
  }
  const B = [-.92, -.60, -.30, .06, .30, .56, .80];
  function project(i, side) { // точка на боковой грани слоя i в пикселях окна
    if (!Mx) return [0, 0];
    const flat = k => -.66 + k * .235, mid = (1 - S.fold) * (flat(i) + flat(i + 1)) / 2 + S.fold * ((B[i] + B[i + 1]) / 2 + (i < 5 ? -.10 : 0)), y = mid + (i - 2.5) * S.explode * .43, p = [X * side * .98, y, Z * .98, 1];
    const a = [0, 0, 0, 0], b = [0, 0, 0, 0]; for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) a[r] += Mx[c * 4 + r] * p[c]; for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) b[r] += Pm[c * 4 + r] * a[c];
    return [(b[0] / b[3] * .5 + .5) * innerWidth, (.5 - b[1] / b[3] * .5) * innerHeight];
  }
  return { ok: true, S, T, frame, project };
})();
