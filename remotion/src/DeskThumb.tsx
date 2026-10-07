import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Img, continueRender, delayRender, staticFile} from 'remotion';
import {loadFont} from '@remotion/google-fonts/BarlowCondensed';

/* The UPSC Desk YouTube thumbnail, 1280 x 720: the approved design system (DeskThumbV2, the
   owner's mockups) with the Essay desk's claret and gold. One hook of at most six words, its
   accent words in gold, under the H2 header (a full-width gold bar naming the exam and the
   paper, the desk and the issue under it). Six layouts, T1 to T6; ops/desk_thumb.py picks one
   per issue and writes the props. Rules: docs/THUMBNAILS.md.

   Changes from the mockup, so that no hook can break a layout: every hook is fitted (measured
   in the loaded font, shrunk until it fits its box), every box ends above y 600 or left of
   x 980 (the bottom-right 300 x 120 is YouTube's timestamp), T6 sits in a bounded box, T4's
   dots moved up out of the timestamp, the plate is optional (a plain claret gradient without
   it), and on the Essay desk T2 and T5 carry the topic's key word instead of a thinker. */
const {fontFamily: COND, waitUntilDone} = loadFont('normal', {weights: ['600', '700', '800'], subsets: ['latin']});
const PAL: Record<string, any> = {
	sociology: {night: '#0E1A2C', deep: '#1E3A5F', soft: '#2C4E76', amber: '#F59E0B', amberSoft: '#F7C46C', cream: '#F4F1EA', mute: '#A8B8CC', motif: '#3C587F',
		desk: 'THE SOCIOLOGY DESK', paper: 'SOCIOLOGY OPTIONAL', stamp: 'THINKER'},
	gs: {night: '#1A1224', deep: '#3E2A52', soft: '#4A3562', amber: '#D2A24C', amberSoft: '#E7C987', cream: '#F6F1E7', mute: '#B9AFC8', motif: '#5E4A73',
		desk: 'THE GS DESK', paper: 'GENERAL STUDIES PAPER', stamp: 'THINKER'},
	essay: {night: '#240E14', deep: '#7A2D3A', soft: '#8F4250', amber: '#E0B35A', amberSoft: '#EBCB82', cream: '#F6EFE3', mute: '#CBB2B8', motif: '#9C5260',
		desk: 'THE ESSAY DESK', paper: 'ESSAY PAPER', stamp: 'KEY WORD'},
};
let C: any = PAL.essay;

type P = {v: string; hook: string; accent: string; thinker: string; issue: string; date: string; plate: string; header?: string; desk?: string};

// ---- fitting: measure in the loaded font, wrap greedily as the browser does, shrink to fit ----
let ctx: CanvasRenderingContext2D | null = null;
const width = (t: string, size: number, weight: number, ls: number) => {
	if (!ctx) ctx = document.createElement('canvas').getContext('2d');
	ctx!.font = `${weight} ${size}px "${COND}"`;
	return ctx!.measureText(t).width + ls * t.length;
};
const wrap = (text: string, size: number, maxW: number, weight: number, ls: number) => {
	const words = text.split(/\s+/).filter(Boolean);
	let lines = 0, cur = '', widest = 0;
	for (const w of words) {
		const next = cur ? `${cur} ${w}` : w;
		if (cur && width(next, size, weight, ls) > maxW) {
			lines++; widest = Math.max(widest, width(cur, size, weight, ls)); cur = w;
		} else cur = next;
	}
	if (cur) { lines++; widest = Math.max(widest, width(cur, size, weight, ls)); }
	return {lines, widest};
};
/** the largest size (at most max) at which text fits maxW x maxH */
const fit = (text: string, o: {maxW: number; maxH: number; max: number; min?: number; lh: number; weight?: number; ls?: number}) => {
	const {maxW, maxH, max, min = 36, lh, weight = 800, ls = 0.5} = o;
	for (let s = max; s > min; s -= 2) {
		const r = wrap(text, s, maxW * 0.97, weight, ls);
		if (r.widest <= maxW * 0.97 && r.lines * s * lh <= maxH) return s;
	}
	return min;
};

/** the hook with its accent words in gold, fitted to its box */
const Hook: React.FC<{p: P; max: number; maxW: number; maxH: number; color?: string; acc?: string; lh?: number; upper?: boolean}> = ({p, max, maxW, maxH, color = C.cream, acc = C.amber, lh = 0.98, upper = true}) => {
	const t = upper ? p.hook.toUpperCase() : p.hook;
	const a = upper ? p.accent.toUpperCase() : p.accent;
	const i = a ? t.indexOf(a) : -1;
	const size = fit(t, {maxW, maxH, max, lh});
	return (
		<div style={{fontFamily: COND, fontWeight: 800, fontSize: size, lineHeight: lh, color, letterSpacing: 0.5, width: maxW}}>
			{i < 0 ? t : <>{t.slice(0, i)}<span style={{color: acc}}>{a}</span>{t.slice(i + a.length)}</>}
		</div>
	);
};

/** the hook's height once fitted (T1 and T3 place their boxes by it) */
const hookHeight = (p: P, o: {max: number; maxW: number; maxH: number; lh?: number; upper?: boolean}) => {
	const lh = o.lh ?? 0.98;
	const t = o.upper === false ? p.hook : p.hook.toUpperCase();
	const s = fit(t, {maxW: o.maxW, maxH: o.maxH, max: o.max, lh});
	return wrap(t, s, o.maxW * 0.97, 800, 0.5).lines * s * lh;
};

/** headers. H0: the approved Sociology header. H1 to H3: the desk and the paper made legible */
const HeaderH0: React.FC<{p: P}> = ({p}) => (
	<div style={{position: 'absolute', left: 48, right: 48, top: 30}}>
		<div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
			<span style={{fontFamily: COND, fontWeight: 800, fontSize: 30, letterSpacing: 3, color: C.cream}}>{C.desk}</span>
			<span style={{fontFamily: COND, fontWeight: 700, fontSize: 28, color: C.amberSoft}}>Issue {p.issue}  ·  {p.date}</span>
		</div>
		<div style={{fontFamily: COND, fontWeight: 800, fontSize: 30, letterSpacing: 2, color: C.amber, marginTop: 4}}>{C.paper}</div>
		<div style={{fontFamily: COND, fontWeight: 700, fontSize: 22, letterSpacing: 3, color: C.cream}}>UPSC CIVIL SERVICES EXAMINATION</div>
	</div>
);
const HeaderH1: React.FC<{p: P}> = ({p}) => (
	<div style={{position: 'absolute', left: 48, right: 48, top: 28}}>
		<div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start'}}>
			<div>
				<div style={{fontFamily: COND, fontWeight: 800, fontSize: 46, letterSpacing: 3, color: C.cream, lineHeight: 1}}>{C.desk}</div>
				<div style={{fontFamily: COND, fontWeight: 700, fontSize: 30, letterSpacing: 2.5, color: C.cream, marginTop: 8, opacity: 0.92}}>UPSC CIVIL SERVICES EXAMINATION</div>
				<div style={{display: 'inline-block', marginTop: 10, background: C.amber, color: C.night, fontFamily: COND, fontWeight: 800, fontSize: 34, letterSpacing: 2.5, padding: '4px 16px', borderRadius: 6}}>{C.paper}</div>
			</div>
			<span style={{fontFamily: COND, fontWeight: 700, fontSize: 28, color: C.amberSoft}}>Issue {p.issue} · {p.date}</span>
		</div>
	</div>
);
// H2 bar (the Essay desk's): a full-width gold bar naming the exam and the paper, the desk and
// the issue under it. It ends at y 74, the line under it at about y 135; no hook starts above 150.
const HeaderH2: React.FC<{p: P}> = ({p}) => (
	<>
		<div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 74, background: C.amber, display: 'flex', alignItems: 'center', padding: '0 48px', justifyContent: 'space-between'}}>
			<span style={{fontFamily: COND, fontWeight: 800, fontSize: 40, letterSpacing: 2.5, color: C.night}}>UPSC CIVIL SERVICES EXAMINATION</span>
			<span style={{fontFamily: COND, fontWeight: 800, fontSize: 40, letterSpacing: 2.5, color: C.night}}>{C.paper}</span>
		</div>
		<div style={{position: 'absolute', left: 48, right: 48, top: 92, display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
			<span style={{fontFamily: COND, fontWeight: 800, fontSize: 38, letterSpacing: 3, color: C.cream}}>{C.desk}</span>
			<span style={{fontFamily: COND, fontWeight: 700, fontSize: 28, color: C.amberSoft}}>Issue {p.issue} · {p.date}</span>
		</div>
	</>
);
const HeaderH3: React.FC<{p: P}> = ({p}) => (
	<div style={{position: 'absolute', left: 48, right: 48, top: 30, display: 'flex', gap: 22, alignItems: 'center'}}>
		<div style={{background: C.amber, color: C.night, borderRadius: 10, padding: '10px 20px', fontFamily: COND, fontWeight: 800, fontSize: 44, letterSpacing: 2, lineHeight: 1, whiteSpace: 'nowrap'}}>{C.paper}</div>
		<div style={{flex: 1}}>
			<div style={{fontFamily: COND, fontWeight: 800, fontSize: 36, letterSpacing: 3, color: C.cream, lineHeight: 1.05}}>{C.desk}</div>
			<div style={{fontFamily: COND, fontWeight: 700, fontSize: 28, letterSpacing: 2.5, color: C.cream, opacity: 0.92}}>UPSC CIVIL SERVICES EXAMINATION</div>
		</div>
		<span style={{alignSelf: 'flex-start', fontFamily: COND, fontWeight: 700, fontSize: 26, color: C.amberSoft, whiteSpace: 'nowrap'}}>Issue {p.issue} · {p.date}</span>
	</div>
);
const HEADERS: Record<string, React.FC<{p: P}>> = {H0: HeaderH0, H1: HeaderH1, H2: HeaderH2, H3: HeaderH3};
const Header: React.FC<{p: P}> = ({p}) => {
	const H = HEADERS[p.header || 'H2'] || HeaderH2;
	return <H p={p} />;
};

/** the art, or a plain claret gradient when there is none */
const Plate: React.FC<{p: P; opacity?: number; fade?: string}> = ({p, opacity = 0.55, fade}) => (
	<>
		{p.plate
			? <Img src={staticFile(p.plate)} style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', opacity}} />
			: <AbsoluteFill style={{background: `radial-gradient(circle at 78% 45%, ${C.soft} 0%, ${C.deep} 40%, ${C.night} 100%)`, opacity: 0.9}} />}
		<AbsoluteFill style={{background: fade || `linear-gradient(90deg, ${C.night} 0%, ${C.night}EE 38%, ${C.deep}99 70%, ${C.deep}55 100%)`}} />
	</>
);

const Dots: React.FC<{x: number; y: number; c?: string}> = ({x, y, c = C.motif}) => (
	<svg width={200} height={200} style={{position: 'absolute', left: x, top: y, opacity: 0.6}}>
		{Array.from({length: 25}, (_, k) => <circle key={k} cx={12 + (k % 5) * 44} cy={12 + Math.floor(k / 5) * 44} r={5} fill={c} />)}
	</svg>
);

// T1: the hook large over the art, accent in gold, a gold rule under it (bottom-anchored, left of x 868)
const T1: React.FC<{p: P}> = ({p}) => (
	<AbsoluteFill style={{background: C.night}}>
		<Plate p={p} />
		<Header p={p} />
		<div style={{position: 'absolute', left: 48, width: 820, bottom: 92}}>
			<Hook p={p} max={112} maxW={820} maxH={434} />
			<div style={{width: 180, height: 12, background: C.amber, marginTop: 22, borderRadius: 6}} />
		</div>
	</AbsoluteFill>
);

// T2: the key word (a thinker on Sociology) as the giant anchor, the hook under it, all above y 590
const T2: React.FC<{p: P}> = ({p}) => {
	const name = p.thinker.toUpperCase();
	const lower = p.hook.toLowerCase(), th = p.thinker.toLowerCase();
	// strip the name only when the hook opens with it; otherwise the hook stays whole
	const rest = (lower.startsWith(th) ? p.hook.slice(p.thinker.length).replace(/^[\s:,'’s]+/, '') : p.hook).trim().toUpperCase();
	const big = fit(name, {maxW: 1184, maxH: 220, max: 200, lh: 0.9, ls: 2});
	const top = 205, restTop = top + big * 0.9 + 14;
	const small = fit(rest, {maxW: 1184, maxH: 590 - restTop, max: 84, lh: 1, weight: 700});
	return (
		<AbsoluteFill style={{background: C.night}}>
			<Plate p={p} opacity={0.45} fade={`linear-gradient(180deg, ${C.night}CC 0%, ${C.night}EE 55%, ${C.night} 100%)`} />
			<Header p={p} />
			<div style={{position: 'absolute', left: 48, width: 1184, top}}>
				<div style={{fontFamily: COND, fontWeight: 800, fontSize: big, lineHeight: 0.9, color: C.amber, letterSpacing: 2}}>{name}</div>
				<div style={{fontFamily: COND, fontWeight: 700, fontSize: small, lineHeight: 1, color: C.cream, marginTop: 14, letterSpacing: 0.5}}>{rest}</div>
			</div>
		</AbsoluteFill>
	);
};

// T3: a full-width gold band carrying the hook in night, the art above it; the band ends by y 600
const T3: React.FC<{p: P}> = ({p}) => {
	const h = hookHeight(p, {max: 100, maxW: 1184, maxH: 290});
	const top = Math.min(330, 600 - 56 - h);
	return (
		<AbsoluteFill style={{background: C.night}}>
			<Plate p={p} opacity={0.6} fade={`linear-gradient(180deg, ${C.night}DD 0%, ${C.deep}66 60%, ${C.night}AA 100%)`} />
			<Header p={p} />
			<div style={{position: 'absolute', left: 0, right: 0, top, background: C.amber, padding: '26px 48px 30px'}}>
				<Hook p={p} max={100} maxW={1184} maxH={290} color={C.night} acc={C.cream} />
			</div>
		</AbsoluteFill>
	);
};

// T4: the hook with an oversized gold quotation mark, plain claret, no art; ends by y 590
const T4: React.FC<{p: P}> = ({p}) => {
	// the dots only where the hook leaves room for them (right of x 1040, above y 570)
	const t = p.hook.toUpperCase(), s = fit(t, {maxW: 980, maxH: 360, max: 110, lh: 0.98});
	const room = 230 + wrap(t, s, 980 * 0.97, 800, 0.5).widest < 1020;
	return (
	<AbsoluteFill style={{background: `linear-gradient(135deg, ${C.deep} 0%, ${C.night} 100%)`}}>
		{room ? <Dots x={1040} y={370} /> : null}
		<Header p={p} />
		<div style={{position: 'absolute', left: 48, top: 170, fontFamily: 'Georgia, serif', fontWeight: 700, fontSize: 300, lineHeight: 1, color: C.amber}}>{'“'}</div>
		<div style={{position: 'absolute', left: 230, top: 230}}>
			<Hook p={p} max={110} maxW={980} maxH={360} />
		</div>
	</AbsoluteFill>
	);
};

// T5: a gold stamp with the key word (a thinker on Sociology), the hook beside it, art behind
const T5: React.FC<{p: P}> = ({p}) => {
	const name = p.thinker.toUpperCase();
	const size = fit(name, {maxW: 250, maxH: 90, max: 72, min: 30, lh: 1});
	return (
		<AbsoluteFill style={{background: C.night}}>
			<Plate p={p} opacity={0.5} />
			<Header p={p} />
			<div style={{position: 'absolute', left: 48, top: 215}}>
				<Hook p={p} max={104} maxW={760} maxH={375} />
			</div>
			<div style={{position: 'absolute', right: 70, top: 230, width: 330, height: 330, borderRadius: 165, border: `10px solid ${C.amber}`,
				display: 'flex', alignItems: 'center', justifyContent: 'center', transform: 'rotate(-8deg)', background: `${C.night}CC`}}>
				<div style={{textAlign: 'center'}}>
					<div style={{fontFamily: COND, fontWeight: 700, fontSize: 30, letterSpacing: 4, color: C.amberSoft}}>{C.stamp}</div>
					<div style={{fontFamily: COND, fontWeight: 800, fontSize: size, lineHeight: 1, color: C.amber}}>{name}</div>
				</div>
			</div>
		</AbsoluteFill>
	);
};

// T6: minimal type on deep claret, one gold phrase, a lot of air; centred in y 160 to 600
const T6: React.FC<{p: P}> = ({p}) => (
	<AbsoluteFill style={{background: C.deep}}>
		<AbsoluteFill style={{background: `radial-gradient(circle at 75% 40%, ${C.soft} 0%, ${C.deep} 45%, ${C.night} 100%)`}} />
		<Header p={p} />
		<div style={{position: 'absolute', left: 48, width: 1184, top: 160, height: 440, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
			<Hook p={p} max={124} maxW={1184} maxH={440} upper={false} lh={1.02} />
		</div>
	</AbsoluteFill>
);

const V: Record<string, React.FC<{p: P}>> = {T1, T2, T3, T4, T5, T6};
export const DeskThumb: React.FC<P> = (p) => {
	// the hooks are measured in the font itself, so nothing renders until it has loaded
	const [handle] = useState(() => delayRender('the thumbnail font'));
	const [ready, setReady] = useState(false);
	useEffect(() => {
		waitUntilDone().then(() => document.fonts.ready).then(() => { setReady(true); continueRender(handle); });
	}, [handle]);
	C = PAL[p.desk || 'essay'] || PAL.essay;
	if (!ready) return null;
	const K = (!p.thinker && (p.v === 'T2' || p.v === 'T5')) ? T1 : (V[p.v] || T1);
	return <K p={p} />;
};
