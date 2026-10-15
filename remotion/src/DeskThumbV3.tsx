import React, {useLayoutEffect, useRef, useState} from 'react';
import {AbsoluteFill, Img, continueRender, delayRender, staticFile} from 'remotion';
import {loadFont} from '@remotion/google-fonts/BarlowCondensed';

/*
 * The desk thumbnails v3 (approved 15 Oct 2026), 1280 x 720: the compact header and the seven
 * formats F1 to F7 of the UPSC Desk thumbnail playbook, in each desk's own palette. The same file
 * is in all three desk repos (sociology, gs, essay); ops/thumb_v3.py writes the props and picks
 * the format from the day's content type and the desk's recent formats (docs/THUMBNAILS.md).
 *
 *   F1 Portrait + Verdict   a thinker (portrait when the library has one, else the name, giant) and a question
 *   F2 Versus               two names either side of a VS disc, the verdict in an accent band
 *   F3 Ladder               three or four steps rising left to right on the desk's tint, grid paper
 *   F4 Stakes Object        one real number on a card (a gauge when it is a share), a drawn arrow
 *   F5 Proof                an answer sheet with the marks before and after
 *   F6 Quiet Statement      a concept or a topic in large type, lots of space
 *   F7 Strike-through       the old thing crossed out over the new thing
 *
 * Every text block has its own box and shrinks until it fits (Fit), so no text runs into another
 * block, a figure or a pattern; nothing is drawn in the bottom-right 300 x 120 (x 980 to 1280,
 * y 600 to 720) where YouTube shows the running time.
 */
const font = loadFont('normal', {weights: ['600', '700', '800'], subsets: ['latin']});
const fontItalic = loadFont('italic', {weights: ['600'], subsets: ['latin']});
const COND = font.fontFamily;

const PAL: Record<string, any> = {
	sociology: {night: '#0E1A2C', deep: '#1E3A5F', soft: '#2C4E76', acc: '#F59E0B', acc2: '#F7C46C', accDeep: '#B26E00', cream: '#F4F1EA',
		mute: '#A8B8CC', motif: '#3C587F', tint: '#DCE8F5', support: '#B8CCE0', ink: '#142038', desk: 'THE SOCIOLOGY DESK'},
	gs: {night: '#1A1224', deep: '#3E2A52', soft: '#4A3562', acc: '#D2A24C', acc2: '#E7C987', accDeep: '#8A6420', cream: '#F6F1E7',
		mute: '#B9AFC8', motif: '#5E4A73', tint: '#ECE6F1', support: '#C3B4D0', ink: '#251633', desk: 'THE GS DESK'},
	essay: {night: '#240E14', deep: '#7A2D3A', soft: '#8F4250', acc: '#E0B35A', acc2: '#EBCB82', accDeep: '#8A6300', cream: '#F6EFE3',
		mute: '#CBB2B8', motif: '#9C5260', tint: '#F6EFE3', support: '#D6B4BC', ink: '#461A22', desk: 'THE ESSAY DESK'},
};
const deskOf = (d?: string) => (d === 'soc' ? 'sociology' : d || 'sociology');

type Side = {name: string; sub?: string};
type Step = {label: string; tag?: string};
export type DeskThumbV3Props = {
	desk: string; f: string; pill?: string; issue?: string; date?: string; plate?: string | null;
	kicker?: string; hook?: string; accent?: string;
	name?: string; portrait?: string | null;                   // F1
	left?: Side; right?: Side; cards?: string[]; pick?: number; // F2
	steps?: Step[];                                            // F3
	number?: string; label?: string; caption?: string; gauge?: number | null; // F4
	before?: number; after?: number; outOf?: number; note?: string; sheet?: string; // F5
	big?: string; sub?: string; line?: string; upper?: boolean; // F6
	old?: string; neu?: string; mode?: string;                 // F7
	[k: string]: any;
};
type P = DeskThumbV3Props;

/** a font size scaled by the box's fit factor (--k, set by Fit) */
const fs = (n: number) => `calc(var(--k, 1) * ${n}px)`;

/** A box w wide and at most h tall. Its children size their type with fs(); the factor starts at 1
    and steps down until nothing in the box overflows it (nowrap lines carry data-fit). */
const Fit: React.FC<{w: number; h: number; min?: number; style?: React.CSSProperties; children: React.ReactNode}> = ({w, h, min = 0.3, style, children}) => {
	const ref = useRef<HTMLDivElement>(null);
	const [handle] = useState(() => delayRender('fit'));
	const [k, setK] = useState(1);
	useLayoutEffect(() => {
		let live = true;
		Promise.all([font.waitUntilDone(), fontItalic.waitUntilDone()]).then(() => {
			const el = ref.current;
			if (!live || !el) return;
			let f = 1;
			const over = () => el.scrollHeight > h + 1 || el.scrollWidth > w + 1 ||
				Array.from(el.querySelectorAll<HTMLElement>('[data-fit]')).some((c) => c.scrollWidth > c.clientWidth + 1);
			el.style.setProperty('--k', String(f));
			while (f > min && over()) {
				f = Math.round((f - 0.02) * 100) / 100;
				el.style.setProperty('--k', String(f));
			}
			setK(f);
			continueRender(handle);
		}).catch(() => continueRender(handle));
		return () => { live = false; };
	}, [w, h, min, handle]);
	return <div ref={ref} style={{width: w, maxHeight: h, overflow: 'hidden', ['--k' as any]: k, overflowWrap: 'normal', wordBreak: 'normal', ...style}}>{children}</div>;
};

/** text with its accent words in another colour (matched without regard to case) */
const Acc: React.FC<{t: string; a?: string; color: string; mark?: boolean}> = ({t, a, color, mark}) => {
	const i = a ? t.toLowerCase().indexOf(a.toLowerCase()) : -1;
	if (i < 0 || !a) return <>{t}</>;
	const hit = t.slice(i, i + a.length);
	return <>{t.slice(0, i)}{mark ? <span style={{background: `linear-gradient(transparent 56%, ${color} 56%)`, padding: '0 0.08em'}}>{hit}</span> : <span style={{color}}>{hit}</span>}{t.slice(i + a.length)}</>;
};

const up = (s?: string) => String(s || '').toUpperCase();

/** the compact header (approved 15 Oct 2026): the desk and a paper pill on one line, issue and date
    top right on current-affairs videos only. It ends at y 84; every format starts at y 110 or below. */
const Header: React.FC<{p: P; C: any; light?: boolean}> = ({p, C, light}) => (
	<>
		<div style={{position: 'absolute', left: 48, top: 40, display: 'flex', alignItems: 'center', gap: 14}}>
			<span style={{fontFamily: COND, fontWeight: 800, fontSize: 32, letterSpacing: 3, color: light ? C.deep : C.cream, lineHeight: 1}}>{C.desk}</span>
			{p.pill ? <span style={{fontFamily: COND, fontWeight: 800, fontSize: 27, letterSpacing: 2, background: C.acc, color: C.night, padding: '3px 12px', borderRadius: 6, lineHeight: 1.1}}>{up(p.pill)}</span> : null}
		</div>
		{p.issue && p.date ? (
			<span style={{position: 'absolute', right: 48, top: 44, fontFamily: COND, fontWeight: 700, fontSize: 26, color: light ? C.deep : C.acc2}}>Issue {p.issue} · {p.date}</span>
		) : null}
	</>
);

const Plate: React.FC<{p: P; C: any; opacity?: number; fade?: string}> = ({p, C, opacity = 0.4, fade}) => {
	const [ok, setOk] = useState(true);
	if (!p.plate || !ok) return null;
	return (
		<>
			<Img src={staticFile(p.plate)} onError={() => setOk(false)} style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', opacity}} />
			<AbsoluteFill style={{background: fade || `linear-gradient(90deg, ${C.night} 0%, ${C.night}F0 45%, ${C.night}B0 100%)`}} />
		</>
	);
};

/** the kicker on its own line (its own box, so a long kicker never shrinks the hook), then the hook */
const Lead: React.FC<{p: P; C: any; w: number; h: number; size: number; underline?: boolean}> = ({p, C, w, h, size, underline = true}) => (
	<>
		{p.kicker ? (
			<Fit w={w} h={44}>
				<div data-fit style={{fontFamily: COND, fontWeight: 700, fontSize: fs(30), lineHeight: 1.2, letterSpacing: 3, color: C.acc2, textTransform: 'uppercase', whiteSpace: 'nowrap'}}>{p.kicker}</div>
			</Fit>
		) : null}
		<div style={{height: p.kicker ? 10 : 0}} />
		<Fit w={w} h={p.kicker ? h - 54 : h}>
			<div style={{fontFamily: COND, fontWeight: 800, fontSize: fs(size), lineHeight: 0.95, color: C.cream, textTransform: 'uppercase'}}>
				<Acc t={p.hook || ''} a={p.accent} color={C.acc} />
			</div>
			{underline ? <Underline C={C} /> : null}
		</Fit>
	</>
);

const Underline: React.FC<{C: any}> = ({C}) => <div style={{width: 180, height: 12, background: C.acc, borderRadius: 6, marginTop: 24}} />;

/** a hand-drawn arrow in the accent colour */
const Arrow: React.FC<{C: any; x: number; y: number; w: number; d?: string; head?: string}> = ({C, x, y, w, d = 'M6 96 C40 92 92 70 118 22', head = 'M98 28 L120 18 L124 42'}) => (
	<svg viewBox="0 0 130 110" style={{position: 'absolute', left: x, top: y, width: w, overflow: 'visible'}}>
		<path d={d} style={{fill: 'none', stroke: C.acc, strokeWidth: 6, strokeLinecap: 'round'}} />
		<path d={head} style={{fill: 'none', stroke: C.acc, strokeWidth: 6, strokeLinecap: 'round', strokeLinejoin: 'round'}} />
	</svg>
);

// ------------------------------------------------------------------ F1 Portrait + Verdict
const F1: React.FC<{p: P; C: any}> = ({p, C}) => {
	const [portraitOk, setPortraitOk] = useState(true);
	const portrait = p.portrait && portraitOk;
	return (
		<AbsoluteFill style={{background: `radial-gradient(circle at 74% 50%, ${C.soft} 0%, ${C.deep} 30%, ${C.night} 78%)`}}>
			{portrait ? (
				// x 620 to 975, bottom-anchored: the shoulders stop short of the running-time corner
				<div style={{position: 'absolute', left: 620, width: 355, top: 110, bottom: 0, background: C.deep, overflow: 'hidden'}}>
					<Img src={staticFile(p.portrait as string)} onError={() => setPortraitOk(false)}
						style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top center', filter: 'grayscale(1) contrast(1.12)', mixBlendMode: 'luminosity'}} />
					<div style={{position: 'absolute', top: 0, bottom: 0, right: 0, width: 8, background: C.acc}} />
				</div>
			) : (
				// no portrait: the name itself is the focal subject, giant, in its own box
				<div style={{position: 'absolute', left: 700, top: 150, width: 530, height: 400, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
					<div style={{fontFamily: COND, fontWeight: 700, fontSize: 28, letterSpacing: 5, color: C.mute, marginBottom: 6}}>THINKER</div>
					<Fit w={530} h={330}>
						<div style={{fontFamily: COND, fontWeight: 800, fontSize: fs(190), lineHeight: 0.88, color: C.acc}}>{up(p.name)}</div>
					</Fit>
					<div style={{width: 120, height: 8, background: C.acc2, marginTop: 18, borderRadius: 4}} />
				</div>
			)}
			<Header p={p} C={C} />
			<div style={{position: 'absolute', left: 48, top: 150}}>
				<Lead p={p} C={C} w={portrait ? 540 : 610} h={430} size={118} />
			</div>
		</AbsoluteFill>
	);
};

// ------------------------------------------------------------------ F2 Versus / Choice
const F2: React.FC<{p: P; C: any}> = ({p, C}) => {
	if (p.cards && p.cards.length >= 3) {
		const n = Math.min(4, p.cards.length);
		const cw = (1100 - (n - 1) * 30) / n;
		return (
			<AbsoluteFill style={{background: `radial-gradient(circle at 50% 75%, ${C.deep} 0%, ${C.night} 70%)`}}>
				<Header p={p} C={C} />
				<div style={{position: 'absolute', left: 48, top: 120, display: 'flex', justifyContent: 'center', width: 1184}}>
					<Fit w={1184} h={110}>
						<div data-fit style={{fontFamily: COND, fontWeight: 800, fontSize: fs(92), lineHeight: 1, color: C.cream, textTransform: 'uppercase', whiteSpace: 'nowrap', textAlign: 'center'}}>
							<Acc t={p.hook || ''} a={p.accent} color={C.acc} />
						</div>
					</Fit>
				</div>
				{p.cards.slice(0, n).map((c, i) => {
					const on = i === (p.pick ?? 0);
					return (
						<div key={i} style={{position: 'absolute', left: 90 + i * (cw + 30), top: on ? 278 : 300, width: cw, height: 250, borderRadius: 14,
							background: on ? C.deep : C.night, border: `${on ? 7 : 3}px solid ${on ? C.acc : C.motif}`, padding: 22, display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
							boxShadow: on ? '0 18px 40px rgba(0,0,0,.45)' : 'none'}}>
							<span style={{fontFamily: COND, fontWeight: 800, fontSize: 50, lineHeight: 1, color: on ? C.acc : C.mute}}>{i + 1}</span>
							<Fit w={cw - 50} h={130}><div style={{fontFamily: COND, fontWeight: 700, fontSize: fs(46), lineHeight: 1.02, color: C.cream}}>{c}</div></Fit>
						</div>
					);
				})}
			</AbsoluteFill>
		);
	}
	const side = (s: Side | undefined, x: number) => (
		<div style={{position: 'absolute', left: x, top: 130, width: 480, height: 270, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center'}}>
			<Fit w={480} h={270}>
				<div style={{fontFamily: COND, fontWeight: 800, fontSize: fs(150), lineHeight: 0.9, color: C.cream, textAlign: 'center'}}>{up(s?.name)}</div>
				{s?.sub ? <div style={{fontFamily: COND, fontWeight: 600, fontSize: fs(36), lineHeight: 1.1, color: C.mute, marginTop: 14, textAlign: 'center'}}>{s.sub}</div> : null}
			</Fit>
		</div>
	);
	return (
		<AbsoluteFill style={{background: `linear-gradient(90deg, ${C.night} 0 50%, ${C.deep} 50% 100%)`}}>
			<Header p={p} C={C} />
			{side(p.left, 60)}
			{side(p.right, 740)}
			<div style={{position: 'absolute', left: 640 - 70, top: 195, width: 140, height: 140, borderRadius: 70, background: C.acc, color: C.night,
				display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: COND, fontWeight: 800, fontSize: 64}}>VS</div>
			{/* the verdict band ends at y 572, above the running-time corner */}
			<div style={{position: 'absolute', left: 0, right: 0, top: 440, height: 132, background: C.acc}} />
			<div style={{position: 'absolute', left: 48, top: 450}}>
				<Fit w={1184} h={112}>
					<div data-fit style={{fontFamily: COND, fontWeight: 800, fontSize: fs(98), lineHeight: 1.08, color: C.night, textTransform: 'uppercase', whiteSpace: 'nowrap', textAlign: 'center'}}>
						<Acc t={p.hook || ''} a={p.accent} color={C.cream} />
					</div>
				</Fit>
			</div>
		</AbsoluteFill>
	);
};

// ------------------------------------------------------------------ F3 Ladder (on the tint)
const F3: React.FC<{p: P; C: any}> = ({p, C}) => {
	const steps = (p.steps || []).slice(0, 4);
	const n = Math.max(3, steps.length);
	const x0 = 150, x1 = 1150, base = 600, rise = n === 4 ? 90 : 110;
	const w = (x1 - x0) / n;
	const tread = (i: number) => ({a: x0 + i * w, b: x0 + (i + 1) * w, y: base - i * rise});
	const pts: string[] = ['40,' + base];
	for (let i = 0; i < n; i++) {
		const t = tread(i);
		if (i > 0) pts.push(`${t.a},${tread(i - 1).y}`);
		pts.push(`${t.a},${t.y}`, `${t.b},${t.y}`);
	}
	return (
		<AbsoluteFill style={{background: C.tint, backgroundImage: `linear-gradient(${C.support}88 2px, transparent 2px), linear-gradient(90deg, ${C.support}88 2px, transparent 2px)`, backgroundSize: '52px 52px'}}>
			<svg viewBox="0 0 1280 720" style={{position: 'absolute', inset: 0}}>
				<polyline points={pts.join(' ')} style={{fill: 'none', stroke: C.deep, strokeWidth: 9, strokeLinejoin: 'round', strokeLinecap: 'round'}} />
			</svg>
			{steps.map((s, i) => {
				const t = tread(i), cx = (t.a + t.b) / 2;
				return (
					<React.Fragment key={i}>
						<div style={{position: 'absolute', left: cx - 22, top: t.y - 48, width: 44, height: 44, borderRadius: 22, background: C.acc, border: `8px solid ${C.deep}`, boxSizing: 'border-box'}} />
						{s.tag ? <div style={{position: 'absolute', left: cx - w / 2 + 10, width: w - 20, top: t.y - 88, textAlign: 'center', fontFamily: COND, fontWeight: 700, fontSize: 24, letterSpacing: 2, color: C.deep}}>{up(s.tag)}</div> : null}
						{/* the label sits under its tread on a solid tint backing, never on the line or the grid */}
						<div style={{position: 'absolute', left: cx - (w - 16) / 2, top: t.y + 16, width: w - 16, display: 'flex', justifyContent: 'center'}}>
							<Fit w={w - 16} h={58} style={{display: 'flex', justifyContent: 'center'}}>
								<span data-fit style={{fontFamily: COND, fontWeight: 800, fontSize: fs(44), lineHeight: 1.15, color: C.ink, background: C.tint, padding: '0 8px', whiteSpace: 'nowrap', textTransform: 'uppercase'}}>{s.label}</span>
							</Fit>
						</div>
					</React.Fragment>
				);
			})}
			<Header p={p} C={C} light />
			{/* the hook's box ends before the second tread's tag and above the stair line */}
			<div style={{position: 'absolute', left: 48, top: 112}}>
				<Fit w={n === 4 ? 460 : 520} h={n === 4 ? 300 : 280}>
					<div style={{display: 'inline-block', background: C.tint, padding: '4px 10px 6px', marginLeft: -10}}>
						<div style={{fontFamily: COND, fontWeight: 800, fontSize: fs(96), lineHeight: 0.98, color: C.ink, textTransform: 'uppercase'}}>
							<Acc t={p.hook || ''} a={p.accent} color={C.acc} mark />
						</div>
					</div>
				</Fit>
			</div>
		</AbsoluteFill>
	);
};

// ------------------------------------------------------------------ F4 Stakes Object
const F4: React.FC<{p: P; C: any}> = ({p, C}) => {
	const g = typeof p.gauge === 'number' && p.gauge >= 0 && p.gauge <= 100 ? p.gauge : null;
	const ang = g === null ? 0 : Math.PI * (1 - g / 100);
	return (
		<AbsoluteFill style={{background: `radial-gradient(circle at 74% 50%, ${C.soft} 0%, ${C.deep} 30%, ${C.night} 78%)`}}>
			<Plate p={p} C={C} opacity={0.25} />
			<Header p={p} C={C} />
			{/* the object: a card, x 700 to 1080, y 120 to 560 */}
			<div style={{position: 'absolute', left: 700, top: 120, width: 380, height: 440, borderRadius: 34, background: '#00000055', border: `6px solid ${C.motif}`,
				transform: 'rotate(4deg)', boxShadow: '0 24px 60px rgba(0,0,0,.5)', padding: '30px 28px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10}}>
				{p.label ? <Fit w={320} h={36} style={{display: 'flex', justifyContent: 'center'}}><span data-fit style={{fontFamily: COND, fontWeight: 700, fontSize: fs(28), letterSpacing: 3, color: C.mute, whiteSpace: 'nowrap'}}>{up(p.label)}</span></Fit> : null}
				{g !== null ? (
					<svg viewBox="0 0 300 165" style={{width: 280}}>
						<path d="M20 150 A130 130 0 0 1 280 150" style={{fill: 'none', stroke: C.motif, strokeWidth: 24}} />
						{g > 0 ? <path d={`M20 150 A130 130 0 0 1 ${150 + 130 * Math.cos(ang)} ${150 - 130 * Math.sin(ang)}`} style={{fill: 'none', stroke: C.acc, strokeWidth: 24}} /> : null}
						<line x1="150" y1="150" x2={150 + 100 * Math.cos(ang)} y2={150 - 100 * Math.sin(ang)} style={{stroke: C.cream, strokeWidth: 8, strokeLinecap: 'round'}} />
						<circle cx="150" cy="150" r="13" style={{fill: C.cream}} />
					</svg>
				) : null}
				<Fit w={320} h={g !== null ? 120 : 210} style={{display: 'flex', justifyContent: 'center'}}>
					<span data-fit style={{fontFamily: COND, fontWeight: 800, fontSize: fs(g !== null ? 120 : 190), lineHeight: 1, color: C.cream, whiteSpace: 'nowrap'}}>{p.number}</span>
				</Fit>
				<div style={{width: '100%', height: 3, background: C.motif}} />
				{p.caption ? <Fit w={320} h={90}><div style={{fontFamily: COND, fontWeight: 600, fontSize: fs(30), lineHeight: 1.15, color: C.mute, textAlign: 'center'}}>{p.caption}</div></Fit> : null}
			</div>
			<Arrow C={C} x={590} y={300} w={110} />
			<div style={{position: 'absolute', left: 48, top: 150}}>
				<Lead p={p} C={C} w={540} h={430} size={120} />
			</div>
		</AbsoluteFill>
	);
};

// ------------------------------------------------------------------ F5 Proof
const F5: React.FC<{p: P; C: any}> = ({p, C}) => (
	<AbsoluteFill style={{background: `radial-gradient(circle at 72% 50%, ${C.soft} 0%, ${C.deep} 32%, ${C.night} 80%)`}}>
		<Header p={p} C={C} />
		{/* the sheet: x 640 to 1150, y 115 to 555, the score circle top right, ruled lines stop short of it */}
		<div style={{position: 'absolute', left: 640, top: 115, width: 510, height: 440, background: '#FBF8F1', transform: 'rotate(-3deg)', boxShadow: '0 24px 50px rgba(0,0,0,.5)',
			backgroundImage: `linear-gradient(90deg, transparent 78px, ${C.support} 78px, ${C.support} 81px, transparent 81px), repeating-linear-gradient(180deg, transparent 0 39px, #E6DED3 39px 41px)`}}>
			<div style={{position: 'absolute', left: 100, top: 26}}><Fit w={220} h={34}><div data-fit style={{fontFamily: COND, fontWeight: 800, fontSize: fs(26), letterSpacing: 2, color: C.deep, whiteSpace: 'nowrap'}}>{up(p.sheet || 'Answer sheet')}</div></Fit></div>
			{[0.52, 0.46, 0.55, 0.78, 0.7, 0.82].map((wd, i) => (
				<div key={i} style={{position: 'absolute', left: 100, top: 82 + i * 40, width: 380 * wd, height: 13, borderRadius: 4, background: '#A79D94',
					boxShadow: i === 1 || i === 4 ? `0 9px 0 -3px ${C.acc}` : 'none'}} />
			))}
			<div style={{position: 'absolute', right: 26, top: 22, width: 150, height: 150, borderRadius: 75, border: `6px solid ${C.accDeep}`, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', lineHeight: 1.02}}>
				<span style={{fontFamily: COND, fontWeight: 700, fontSize: 32, color: C.deep, textDecoration: 'line-through'}}>{p.before}</span>
				<span style={{fontFamily: COND, fontWeight: 800, fontSize: 60, color: C.deep}}>{p.after}</span>
				<span style={{fontFamily: COND, fontWeight: 600, fontSize: 22, color: C.deep}}>/ {p.outOf}</span>
			</div>
			{p.note ? (
				<div style={{position: 'absolute', left: 100, top: 340}}>
					<Fit w={380} h={80}><div style={{fontFamily: COND, fontStyle: 'italic', fontWeight: 600, fontSize: fs(34), lineHeight: 1.1, color: C.accDeep}}>+ {p.note}</div></Fit>
				</div>
			) : null}
		</div>
		<div style={{position: 'absolute', left: 48, top: 160}}>
			<Lead p={p} C={C} w={540} h={420} size={122} underline={false} />
		</div>
	</AbsoluteFill>
);

// ------------------------------------------------------------------ F6 Quiet Statement
const F6: React.FC<{p: P; C: any}> = ({p, C}) => (
	<AbsoluteFill style={{background: `radial-gradient(circle at 80% 30%, ${C.soft} 0%, ${C.deep} 40%, ${C.night} 100%)`}}>
		<Header p={p} C={C} />
		{/* one column, x 48 to 1232, y 140 to 590 */}
		<div style={{position: 'absolute', left: 48, top: 140}}>
			{p.kicker ? <Fit w={1184} h={44}><div data-fit style={{fontFamily: COND, fontWeight: 700, fontSize: fs(30), lineHeight: 1.2, letterSpacing: 3, color: C.acc2, textTransform: 'uppercase', whiteSpace: 'nowrap'}}>{p.kicker}</div></Fit> : null}
			<div style={{height: p.kicker ? 10 : 0}} />
			<Fit w={1184} h={p.kicker ? 396 : 450}>
				<div style={{fontFamily: COND, fontWeight: 800, fontSize: fs(150), lineHeight: 0.95, color: C.cream, textTransform: p.upper ? 'uppercase' : 'none'}}>
					<Acc t={p.big || ''} a={p.line ? undefined : p.accent} color={C.acc} />
				</div>
				{p.sub ? <div data-fit style={{fontFamily: COND, fontWeight: 600, fontSize: fs(36), color: C.mute, marginTop: 16, whiteSpace: 'nowrap'}}>{p.sub}</div> : null}
				<Underline C={C} />
				{p.line ? (
					<div style={{fontFamily: COND, fontWeight: 700, fontSize: fs(78), lineHeight: 1.02, color: C.cream, marginTop: 26}}>
						<Acc t={p.line} a={p.accent} color={C.acc} />
					</div>
				) : null}
			</Fit>
		</div>
	</AbsoluteFill>
);

// ------------------------------------------------------------------ F7 Strike-through
const Mark: React.FC<{ok: boolean; C: any}> = ({ok, C}) => (
	<svg viewBox="0 0 40 40" style={{width: 54, height: 54, flex: 'none'}}>
		{ok ? <path d="M6 21 L16 31 L34 9" style={{fill: 'none', stroke: C.acc, strokeWidth: 6, strokeLinecap: 'round', strokeLinejoin: 'round'}} />
			: <path d="M9 9 L31 31 M31 9 L9 31" style={{fill: 'none', stroke: C.acc, strokeWidth: 6, strokeLinecap: 'round'}} />}
	</svg>
);

const F7: React.FC<{p: P; C: any}> = ({p, C}) => {
	const hook = (
		<div style={{position: 'absolute', left: 48, top: 112}}>
			<Fit w={1184} h={118}>
				<div data-fit style={{fontFamily: COND, fontWeight: 800, fontSize: fs(108), lineHeight: 1.05, color: C.cream, textTransform: 'uppercase', whiteSpace: 'nowrap'}}>
					<Acc t={p.hook || ''} a={p.accent} color={C.acc} />
				</div>
			</Fit>
		</div>
	);
	if (p.mode === 'cards') {
		return (
			<AbsoluteFill style={{background: `linear-gradient(135deg, ${C.deep} 0%, ${C.night} 100%)`}}>
				<Header p={p} C={C} />
				{hook}
				<div style={{position: 'absolute', left: 100, top: 290, width: 360, height: 260, borderRadius: 14, background: C.night, border: `4px solid ${C.motif}`, transform: 'rotate(-3deg)', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden'}}>
					<Fit w={310} h={200} style={{display: 'flex', justifyContent: 'center'}}><span data-fit style={{fontFamily: COND, fontWeight: 800, fontSize: fs(120), lineHeight: 1, color: C.mute, whiteSpace: 'nowrap'}}>{up(p.old)}</span></Fit>
					<div style={{position: 'absolute', left: -20, right: -20, top: '48%', height: 14, background: C.acc, transform: 'rotate(-14deg)'}} />
				</div>
				<Arrow C={C} x={490} y={385} w={140} d="M6 30 L118 30" head="M96 10 L120 30 L96 50" />
				<div style={{position: 'absolute', left: 660, top: 280, width: 380, height: 270, borderRadius: 14, background: C.soft, border: `7px solid ${C.acc}`, transform: 'rotate(2deg)', boxShadow: '0 20px 40px rgba(0,0,0,.45)', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
					<Fit w={330} h={210} style={{display: 'flex', justifyContent: 'center'}}><span data-fit style={{fontFamily: COND, fontWeight: 800, fontSize: fs(130), lineHeight: 1, color: C.cream, whiteSpace: 'nowrap'}}>{up(p.neu)}</span></Fit>
				</div>
			</AbsoluteFill>
		);
	}
	const strip = (t: string | undefined, ok: boolean, top: number) => (
		<div style={{position: 'absolute', left: 48, top, width: 1184, height: 128, borderRadius: 14, background: ok ? C.deep : '#00000040',
			borderLeft: ok ? `14px solid ${C.acc}` : 'none', display: 'flex', alignItems: 'center', gap: 24, padding: '0 30px', boxSizing: 'border-box'}}>
			<Mark ok={ok} C={C} />
			<Fit w={1040} h={110} style={{display: 'flex', alignItems: 'center'}}>
				<span style={{fontFamily: COND, fontStyle: 'italic', fontWeight: 600, fontSize: fs(54), lineHeight: 1.12, color: ok ? C.cream : C.mute,
					textDecoration: ok ? 'none' : 'line-through', textDecorationColor: C.acc, textDecorationThickness: 7}}>"{t}"</span>
			</Fit>
		</div>
	);
	return (
		<AbsoluteFill style={{background: `linear-gradient(135deg, ${C.deep} 0%, ${C.night} 100%)`}}>
			<Header p={p} C={C} />
			{hook}
			{strip(p.old, false, 268)}
			{strip(p.neu, true, 420)}
		</AbsoluteFill>
	);
};

const F: Record<string, React.FC<{p: P; C: any}>> = {F1, F2, F3, F4, F5, F6, F7};
export const DeskThumbV3: React.FC<P> = (p) => {
	const C = PAL[deskOf(p.desk)] || PAL.sociology;
	const K = F[p.f] || F6;
	return <K p={p} C={C} />;
};
