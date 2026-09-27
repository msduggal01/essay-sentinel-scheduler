import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {loadFont} from '@remotion/google-fonts/Poppins';
import {loadFont as loadHand} from '@remotion/google-fonts/Handlee';

/*
 * Instagram and Facebook carousels, 1080 x 1350 (and 1080 x 1080 single cards), built only from
 * the brief element catalogue (upsc-desk-design BRIEF_ELEMENTS.md): a carousel reads like a page
 * of the desk's PDF brief. One slide per still; slide i of n is rendered from the same props.
 * The words come from the day's checked content; nothing here writes copy of its own.
 */
const ARIAL = "Arial, Helvetica, 'Liberation Sans', sans-serif";
const {fontFamily: POPPINS} = loadFont('normal', {weights: ['400', '600', '700'], subsets: ['latin']});
// the desks set in Arial like their briefs; the all-desk umbrella posts in Poppins, like the channel identity
let F = ARIAL;
// the answer and essay text is in the owner's reference handwriting; nothing else changes
const {fontFamily: HAND} = loadHand('normal', {weights: ['400'], subsets: ['latin']});
const SERIF = "Georgia, 'Times New Roman', serif";

const THEMES = {
	gs: {name: 'THE GS DESK', tag: 'General Studies, decoded', primary: '#3E2A52', deep: '#251633', accent: '#D2A24C', accentDeep: '#A67A2E',
		tint: '#ECE6F1', support: '#C3B4D0', motif: '#5E4A73', pale: '#FBF1DC', paler: '#FDF9F0', soft: '#F4F0F8', hl: '#F7E08A', gain: '#C6FF3D'},
	sociology: {name: 'THE SOCIOLOGY DESK', tag: 'Current Affairs through a Sociological Lens', primary: '#1E3A5F', deep: '#142038', accent: '#F59E0B', accentDeep: '#B26E00',
		tint: '#DCE8F5', support: '#B8CCE0', motif: '#3C587F', pale: '#FDF3DF', paler: '#FEF9EE', soft: '#EEF3FA', hl: '#FFE3A3', gain: '#9BE564'},
	essay: {name: 'THE ESSAY DESK', tag: 'UPSC Essay, decoded', primary: '#7A2D3A', deep: '#461A22', accent: '#B8860B', accentDeep: '#8A6300',
		tint: '#F6EFE3', support: '#D6B4BC', motif: '#78464E', pale: '#F6EFDF', paler: '#FBF7EE', soft: '#F7EEEE', hl: '#F3DE9E', gain: '#FFA630'},
	// all-desk posts only: the dark Sociology-steel to GS-plum gradient, gold, no Essay claret
	umbrella: {name: 'UPSC DESK', tag: 'Write. Get evaluated. Improve.', primary: '#2C2F5E', deep: '#1E3A5F', accent: '#F2C66A', accentDeep: '#A8812C',
		tint: '#E7E9F3', support: '#C3C6DA', motif: '#4A4F86', pale: '#FBF3DF', paler: '#FDF9F0', soft: '#F1F2F8', hl: '#F7E08A', gain: '#C6FF3D'},
};
const band = (C: T) => (C.name === 'UPSC DESK' ? 'linear-gradient(135deg, #1E3A5F 0%, #2C2F5E 50%, #3E2A52 100%)' : C.primary);
type T = (typeof THEMES)['gs'];
const INK = '#1A1D22', MUTED = '#5B6270', RED = '#B8322A', GREEN = '#2F6B3A';
// margin-note headings (catalogue element 15): one uniform pale box, only the headings coloured
const NOTE_COLOURS: Record<string, string> = {'WHY IT SCORES': GREEN, ADD: '#1E3A5F', AVOID: RED, EXAMPLE: '#8A6300', 'CURRENT AFFAIRS': '#5E4A73'};

/** "*word*" bold in the accent's deep shade; "_word_" highlighted (elements 1 and 3) */
const Rich: React.FC<{text: string; C: T}> = ({text, C}) => (
	<>{String(text).split(/(\*[^*]+\*|_[^_]+_)/).map((p, k) =>
		p.startsWith('*') && p.endsWith('*') ? <b key={k} style={{color: C.primary}}>{p.slice(1, -1)}</b>
		: p.startsWith('_') && p.endsWith('_') ? <span key={k} style={{background: C.hl, padding: '0 4px'}}>{p.slice(1, -1)}</span>
		: <span key={k}>{p}</span>)}</>
);
const Label: React.FC<{C: T; children: React.ReactNode; color?: string}> = ({C, children, color}) => (
	<div style={{fontFamily: F, fontWeight: 700, fontSize: 28, letterSpacing: 2, color: color || C.accentDeep, textTransform: 'uppercase'}}>{children}</div>
);
const H: React.FC<{C: T; children: React.ReactNode; size?: number}> = ({C, children, size = 56}) => (
	<div style={{fontFamily: F, fontWeight: 700, fontSize: size, lineHeight: 1.15, color: C.primary, marginTop: 10}}>{children}</div>
);
/** element 6: a box with a coloured rule */
const Box: React.FC<{C: T; rule?: string; fill?: string; border?: string; children: React.ReactNode; style?: React.CSSProperties}> = ({C, rule, fill, border, children, style}) => (
	<div style={{background: fill || C.pale, borderLeft: rule ? `10px solid ${rule}` : undefined, border: border ? `3px solid ${border}` : undefined,
		borderRadius: 6, padding: '28px 32px', ...style}}>{children}</div>
);
/** element 8: pills and tags */
const Pills: React.FC<{C: T; items: string[]}> = ({C, items}) => (
	<div style={{display: 'flex', gap: 14, flexWrap: 'wrap'}}>
		{items.map((t, k) => (
			<span key={k} style={{fontFamily: F, fontWeight: 700, fontSize: 26, padding: '8px 20px', borderRadius: 30,
				background: k === 0 ? C.primary : k === 1 ? C.accent : C.tint, color: k === 0 ? '#fff' : k === 1 ? C.deep : C.primary}}>{t}</span>
		))}
	</div>
);
const Body: React.FC<{children: React.ReactNode; size?: number; color?: string; style?: React.CSSProperties}> = ({children, size = 40, color = INK, style}) => (
	<div style={{fontFamily: F, fontSize: size, lineHeight: 1.45, color, ...style}}>{children}</div>
);

/** every content page sits centred between the band header and the footer */
const PAGE = (x: number): React.CSSProperties => ({position: 'absolute', left: x, right: x, top: 150, bottom: 100, display: 'flex', flexDirection: 'column', justifyContent: 'center'});

// ------------------------------------------------------------------ slide kinds
/** cover: the band header large, pills (8) and the one-line takeaway (10) */
const Cover: React.FC<{s: any; C: T}> = ({s, C}) => (
	<AbsoluteFill>
		<div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 780, background: band(C)}}>
			<svg width={300} height={300} style={{position: 'absolute', right: 60, top: 170, opacity: 0.55}}>
				{Array.from({length: 25}, (_, k) => <circle key={k} cx={30 + (k % 5) * 60} cy={30 + Math.floor(k / 5) * 60} r={6} fill={C.motif} />)}
			</svg>
			<div style={{position: 'absolute', left: 72, right: 72, top: 250}}>
				<span style={{fontFamily: F, fontWeight: 700, fontSize: 28, letterSpacing: 3, padding: '10px 22px', borderRadius: 30, background: C.accent, color: C.deep}}>{s.kicker}</span>
				<div style={{fontFamily: F, fontWeight: 700, fontSize: s.size || 92, lineHeight: 1.08, color: '#fff', marginTop: 40}}>
					{String(s.headline).split(/(\*[^*]+\*)/).map((p, k) => p.startsWith('*') ? <span key={k} style={{color: C.accent}}>{p.slice(1, -1)}</span> : <span key={k}>{p}</span>)}
				</div>
			</div>
			<div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 12, background: C.accent}} />
		</div>
		<div style={{position: 'absolute', left: 72, right: 72, top: 840}}>
			{s.pills ? <Pills C={C} items={s.pills} /> : null}
			<Box C={C} rule={C.accent} style={{marginTop: 34}}>
				<Label C={C}>{s.takeLabel || 'In one line'}</Label>
				<Body size={40} style={{marginTop: 10}}><Rich text={s.takeaway} C={C} /></Body>
			</Box>
		</div>
	</AbsoluteFill>
);

/** element 7: pipeline with arrows, vertical for a portrait slide; the last box filled */
const Pipeline: React.FC<{s: any; C: T}> = ({s, C}) => {
	const steps: any[] = s.steps || [];
	return (
		<div style={{...PAGE(72)}}>
			<Label C={C}>{s.label}</Label>
			<H C={C}>{s.title}</H>
			<div style={{marginTop: 30}}>
				{steps.map((st, k) => {
					const last = k === steps.length - 1;
					return (
						<div key={k}>
							<div style={{display: 'flex', gap: 26, alignItems: 'stretch', background: last ? C.accent : C.soft, border: `3px solid ${last ? C.accent : C.support}`,
								borderRadius: 10, padding: '20px 26px'}}>
								<div style={{width: 230, flexShrink: 0, fontFamily: F, fontWeight: 700, fontSize: 24, letterSpacing: 2, color: last ? C.deep : C.accentDeep, paddingTop: 6}}>{st.k}</div>
								<div>
									<div style={{fontFamily: F, fontWeight: 700, fontSize: 36, color: last ? C.deep : C.primary}}>{st.head}</div>
									{st.body ? <div style={{fontFamily: F, fontSize: 28, lineHeight: 1.35, color: last ? C.deep : MUTED, marginTop: 4}}>{st.body}</div> : null}
								</div>
							</div>
							{!last ? <svg width={60} height={44} style={{display: 'block', marginLeft: 130}}><path d="M30 2 V34 M18 24 L30 40 L42 24" stroke={C.accent} strokeWidth={5} fill="none" /></svg> : null}
						</div>
					);
				})}
			</div>
		</div>
	);
};

/** elements 11 and 6: the question box, directive underlined, key phrases bold, a trap note */
const Question: React.FC<{s: any; C: T}> = ({s, C}) => {
	let parts: {t: string; m?: any}[] = [{t: s.question}];
	for (const m of s.marks || []) {
		parts = parts.flatMap((p) => {
			if (p.m || !p.t.includes(m.text)) return [p];
			const [a, ...rest] = p.t.split(m.text);
			return [{t: a}, {t: m.text, m}, {t: rest.join(m.text)}];
		});
	}
	return (
		<div style={{...PAGE(72)}}>
			<Label C={C}>The probable question</Label>
			<Box C={C} rule={C.accent} style={{marginTop: 18, padding: '36px 38px'}}>
				<div style={{fontFamily: F, fontWeight: 700, fontSize: s.qsize || 42, lineHeight: 1.42, color: INK}}>
					{'“'}{parts.map((p, k) => !p.m ? <span key={k}>{p.t}</span>
						: p.m.kind === 'ul' ? <span key={k} style={{textDecoration: `underline ${C.accentDeep} 5px`, textUnderlineOffset: 8}}>{p.t}</span>
						: <span key={k} style={{background: C.hl, padding: '0 4px'}}>{p.t}</span>)}{'”'}
				</div>
				<div style={{marginTop: 26}}><Pills C={C} items={s.pills || []} /></div>
			</Box>
			{s.trap ? (
				<Box C={C} rule={RED} fill="#FBEDEB" style={{marginTop: 34}}>
					<Label C={C} color={RED}>The trap in this question</Label>
					<Body size={38} style={{marginTop: 10}}><Rich text={s.trap} C={C} /></Body>
				</Box>
			) : null}
		</div>
	);
};

/** element 15: the answer with numbered highlights, notes in one uniform pale box, coloured headings */
const Answer: React.FC<{s: any; C: T}> = ({s, C}) => {
	let n = 0; const notes: {h: string; t: string}[] = [];
	return (
		<div style={{...PAGE(60)}}>
			<div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
				<Label C={C}>{s.label}</Label>
				{s.score ? <span style={{fontFamily: F, fontWeight: 700, fontSize: 44, color: RED}}>{s.score}</span> : null}
			</div>
			<div style={{fontFamily: HAND, wordSpacing: '0.14em', fontSize: s.fs || 38, lineHeight: 1.6, color: INK, marginTop: 16}}>
				{(s.parts || []).map((p: any, k: number) => {
					if (!p.h) return <span key={k}>{p.t}</span>;
					n += 1; notes.push({h: p.h, t: p.note});
					const sup = <sup style={{color: RED, fontWeight: 700, fontSize: '0.6em', marginLeft: 2}}>{n}</sup>;
					return p.strike
						? <span key={k}><span style={{textDecoration: `line-through ${RED} 4px`, color: '#6B6B6B'}}>{p.t}</span>{sup}</span>
						: <span key={k}><span style={{background: C.hl, padding: '0 3px'}}>{p.t}</span>{sup}</span>;
				})}
			</div>
			<div style={{marginTop: 30, background: '#FDF6DC', border: '2px solid #EAD9A0', borderRadius: 6, padding: '22px 28px'}}>
				{notes.map((x, k) => (
					<div key={k} style={{fontFamily: F, fontSize: s.nfs || 30, lineHeight: 1.4, color: INK, marginTop: k ? 14 : 0}}>
						<b style={{color: NOTE_COLOURS[x.h] || C.accentDeep}}>{k + 1} {x.h}.</b> {x.t}
					</div>
				))}
			</div>
		</div>
	);
};

/** element 12: most write, what scores */
const MostWrite: React.FC<{s: any; C: T}> = ({s, C}) => (
	<div style={{...PAGE(72)}}>
		<Label C={C}>{s.label}</Label>
		<H C={C}>{s.title}</H>
		<div style={{marginTop: 30, border: `3px solid ${C.support}`, borderRadius: 8, overflow: 'hidden'}}>
			<div style={{display: 'flex', background: C.primary}}>
				<div style={{flex: 1, padding: '16px 24px', fontFamily: F, fontWeight: 700, fontSize: 26, letterSpacing: 2, color: '#fff'}}>MOST WRITE</div>
				<div style={{flex: 1.15, padding: '16px 24px', fontFamily: F, fontWeight: 700, fontSize: 26, letterSpacing: 2, color: C.accent}}>WHAT SCORES</div>
			</div>
			{(s.pairs || []).map((p: any, k: number) => (
				<div key={k} style={{display: 'flex', background: k % 2 ? C.soft : '#fff', borderTop: `2px solid ${C.support}`}}>
					<div style={{flex: 1, padding: '22px 24px', fontFamily: F, fontSize: 32, lineHeight: 1.35, color: RED, textDecoration: `line-through ${RED} 3px`}}>{p.a}</div>
					<div style={{flex: 1.15, padding: '22px 24px', fontFamily: F, fontWeight: 700, fontSize: 32, lineHeight: 1.35, color: GREEN}}>{p.b}</div>
				</div>
			))}
		</div>
	</div>
);

/** element 13: the marks ladder, each step a move and its marks */
const Ladder: React.FC<{s: any; C: T}> = ({s, C}) => {
	const rows: any[] = s.rows || [];
	let m = s.before;
	return (
		<div style={{...PAGE(72)}}>
			<Label C={C}>{s.label}</Label>
			<H C={C}>{s.title}</H>
			<div style={{marginTop: 26, display: 'flex', flexDirection: 'column-reverse', gap: 14}}>
				<div style={{display: 'flex', alignItems: 'center', gap: 22}}>
					<span style={{width: 130, textAlign: 'center', fontFamily: F, fontWeight: 700, fontSize: 48, color: RED}}>{s.before}</span>
					<Body size={30} color={MUTED}>{s.startNote || 'The answer as written'}</Body>
				</div>
				{rows.map((r, k) => {
					m += r.gain;
					return (
						<div key={k} style={{display: 'flex', alignItems: 'stretch', gap: 22, marginLeft: (k + 1) * 34}}>
							<div style={{width: 130, flexShrink: 0, background: k === rows.length - 1 ? C.accent : C.primary, color: k === rows.length - 1 ? C.deep : '#fff',
								borderRadius: 8, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'}}>
								<span style={{fontFamily: F, fontWeight: 700, fontSize: 44}}>{m}</span>
								<span style={{fontFamily: F, fontWeight: 700, fontSize: 22, background: C.gain, color: '#1A1D22', borderRadius: 12, padding: '0 10px', marginBottom: 6}}>+{r.gain}</span>
							</div>
							<Box C={C} fill={C.soft} style={{flex: 1, padding: '16px 22px'}}>
								<div style={{fontFamily: F, fontWeight: 700, fontSize: 32, color: C.primary}}>{r.head}</div>
								<div style={{fontFamily: F, fontSize: 26, lineHeight: 1.35, color: MUTED, marginTop: 4}}>{r.body}</div>
							</Box>
						</div>
					);
				})}
			</div>
			<div style={{fontFamily: F, fontWeight: 700, fontSize: 30, color: C.primary, marginTop: 20, textAlign: 'right'}}>out of {s.outOf}</div>
		</div>
	);
};

/** element 14: the word budget as one segmented bar */
const Budget: React.FC<{s: any; C: T}> = ({s, C}) => {
	const seg: any[] = s.segments || []; const tot = seg.reduce((a, b) => a + b.n, 0);
	const fills = [C.primary, C.motif, C.accent, C.accentDeep, C.support, C.deep];
	return (
		<div style={{...PAGE(72)}}>
			<Label C={C}>{s.label}</Label>
			<H C={C}>{s.title}</H>
			<div style={{display: 'flex', height: 90, borderRadius: 8, overflow: 'hidden', marginTop: 36}}>
				{seg.map((g, k) => <div key={k} style={{width: `${(g.n / tot) * 100}%`, background: fills[k % fills.length], color: k === 2 || k === 4 ? INK : '#fff',
					display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: F, fontWeight: 700, fontSize: 28}}>{g.n}</div>)}
			</div>
			<div style={{marginTop: 30}}>
				{seg.map((g, k) => (
					<div key={k} style={{display: 'flex', gap: 20, alignItems: 'flex-start', marginTop: 20}}>
						<span style={{width: 34, height: 34, borderRadius: 6, background: fills[k % fills.length], flexShrink: 0, marginTop: 6}} />
						<div>
							<div style={{fontFamily: F, fontWeight: 700, fontSize: 34, color: C.primary}}>{g.label} <span style={{color: MUTED, fontWeight: 400}}>· {g.n} words</span></div>
							{g.body ? <div style={{fontFamily: F, fontSize: 28, lineHeight: 1.35, color: MUTED}}>{g.body}</div> : null}
						</div>
					</div>
				))}
			</div>
		</div>
	);
};

/** elements 16 and 17: the concept card and the quote to reproduce */
const Card: React.FC<{s: any; C: T; square?: boolean}> = ({s, C, square}) => (
	<div style={{...PAGE(72)}}>
		<Label C={C}>{s.label || 'Concept card'}</Label>
		<Box C={C} fill="#fff" border={C.support} style={{marginTop: 16, borderTop: `12px solid ${C.primary}`}}>
			<div style={{fontFamily: F, fontWeight: 700, fontSize: 58, color: C.primary}}>{s.term}</div>
			{(s.rows || []).map((r: any, k: number) => (
				<div key={k} style={{display: 'flex', gap: 20, marginTop: 20}}>
					<div style={{width: 170, flexShrink: 0, fontFamily: F, fontWeight: 700, fontSize: 24, letterSpacing: 2, color: C.accentDeep, paddingTop: 6}}>{r.k}</div>
					<Body size={square ? 30 : 34}><Rich text={r.v} C={C} /></Body>
				</div>
			))}
		</Box>
		{s.quote ? (
			<Box C={C} rule={C.accent} style={{marginTop: 30}}>
				<div style={{fontFamily: SERIF, fontStyle: 'italic', fontSize: square ? 36 : 42, lineHeight: 1.4, color: INK}}>{'“'}{s.quote}{'”'}</div>
				<div style={{fontFamily: F, fontSize: 26, color: MUTED, marginTop: 12}}>{s.quoteBy}</div>
			</Box>
		) : null}
	</div>
);

/** element 19: hub and spokes, clockwise */
const Lens: React.FC<{s: any; C: T}> = ({s, C}) => {
	const L: any[] = (s.lenses || []).slice(0, 6);
	const hub = {x: 540, y: 770};
	const pos = [[540, 420], [855, 590], [855, 950], [540, 1115], [225, 950], [225, 590]];
	return (
		<AbsoluteFill>
			<div style={{position: 'absolute', left: 72, right: 72, top: 176}}>
				<Label C={C}>{s.label}</Label>
				<H C={C} size={48}>{s.title}</H>
			</div>
			<svg width={1080} height={1350} style={{position: 'absolute', left: 0, top: 0}}>
				{L.map((_, k) => <line key={k} x1={hub.x} y1={hub.y} x2={pos[k][0]} y2={pos[k][1]} stroke={C.accent} strokeWidth={4} />)}
			</svg>
			<div style={{position: 'absolute', left: hub.x - 150, top: hub.y - 150, width: 300, height: 300, borderRadius: 150, background: C.primary,
				border: `8px solid ${C.accent}`, boxSizing: 'border-box', display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: 30,
				fontFamily: F, fontWeight: 700, fontSize: 34, lineHeight: 1.15, color: '#fff'}}>{s.hub}</div>
			{L.map((l, k) => (
				<div key={k} style={{position: 'absolute', left: pos[k][0] - 170, top: pos[k][1] - 64, width: 340, minHeight: 128, boxSizing: 'border-box',
					background: C.soft, border: `3px solid ${C.support}`, borderTop: `8px solid ${C.primary}`, borderRadius: 8, padding: '14px 18px', textAlign: 'center'}}>
					<div style={{fontFamily: F, fontWeight: 700, fontSize: 24, color: C.accentDeep}}>{k + 1}</div>
					<div style={{fontFamily: F, fontWeight: 700, fontSize: 32, color: C.primary}}>{l.title}</div>
					<div style={{fontFamily: F, fontSize: 24, lineHeight: 1.3, color: MUTED, marginTop: 4}}>{l.sub}</div>
				</div>
			))}
		</AbsoluteFill>
	);
};

/** element 21: the opening, rewritten */
const Opening: React.FC<{s: any; C: T}> = ({s, C}) => (
	<div style={{...PAGE(72)}}>
		<Label C={C}>{s.label || 'The opening, rewritten'}</Label>
		<H C={C}>{s.title}</H>
		<Box C={C} rule={RED} fill="#FBEDEB" style={{marginTop: 30}}>
			<Label C={C} color={RED}>The flat opening</Label>
			<Body size={40} color="#6B6B6B" style={{marginTop: 10, fontFamily: HAND, wordSpacing: '0.14em', textDecoration: `line-through ${RED} 3px`}}>{s.flat}</Body>
			{s.why ? <Body size={28} color={RED} style={{marginTop: 12, fontStyle: 'italic'}}>{s.why}</Body> : null}
		</Box>
		<Box C={C} rule={GREEN} fill="#EEF6EF" style={{marginTop: 26}}>
			<Label C={C} color={GREEN}>The working opening</Label>
			<Body size={42} style={{marginTop: 10, fontFamily: HAND, wordSpacing: '0.14em'}}><Rich text={s.working} C={C} /></Body>
			{s.works ? <Body size={28} color={GREEN} style={{marginTop: 12, fontStyle: 'italic'}}>{s.works}</Body> : null}
		</Box>
	</div>
);

/** element 23: anchors that argue (also the lines that score) */
const Anchors: React.FC<{s: any; C: T}> = ({s, C}) => (
	<div style={{...PAGE(72)}}>
		<Label C={C}>{s.label}</Label>
		<H C={C}>{s.title}</H>
		{(s.rows || []).map((r: any, k: number) => (
			<Box key={k} C={C} rule={C.primary} fill={C.soft} style={{marginTop: 24}}>
				<div style={{display: 'flex', justifyContent: 'space-between', gap: 20}}>
					<div style={{fontFamily: F, fontWeight: 700, fontStyle: r.italic ? 'italic' : 'normal', fontSize: 30, color: C.primary}}>{r.source}</div>
					{r.tag ? <span style={{fontFamily: F, fontWeight: 700, fontSize: 22, background: C.accent, color: C.deep, borderRadius: 20, padding: '4px 14px', alignSelf: 'flex-start'}}>{r.tag}</span> : null}
				</div>
				<Body size={34} style={{marginTop: 8}}><Rich text={r.line} C={C} /></Body>
				{r.why ? <Body size={26} color={MUTED} style={{marginTop: 8}}>{r.why}</Body> : null}
			</Box>
		))}
	</div>
);

/** elements 25 and 28: the common mistake (red) with the difficulty and probability meters */
const Mistake: React.FC<{s: any; C: T}> = ({s, C}) => (
	<div style={{...PAGE(72)}}>
		<Box C={C} rule={RED} fill="#FBEDEB">
			<Label C={C} color={RED}>Common mistake</Label>
			<div style={{fontFamily: F, fontWeight: 700, fontSize: 48, lineHeight: 1.2, color: INK, marginTop: 12}}>{s.title}</div>
			{(s.paras || []).map((p: string, k: number) => <Body key={k} size={36} style={{marginTop: 18}}><Rich text={p} C={C} /></Body>)}
		</Box>
		{(s.meters || []).map((m: any, k: number) => (
			<div key={k} style={{marginTop: k ? 26 : 50, display: 'flex', gap: 24, alignItems: 'center'}}>
				<div style={{width: 260, flexShrink: 0}}><Label C={C}>{m.k}</Label></div>
				<div style={{display: 'flex', gap: 12}}>{[0, 1, 2, 3, 4].map((d) => <span key={d} style={{width: 34, height: 34, borderRadius: 17, background: d < m.v ? C.accent : C.tint, border: `2px solid ${C.support}`}} />)}</div>
				<Body size={28} color={MUTED}>{m.why}</Body>
			</div>
		))}
	</div>
);

/** element 27: before you submit */
const Checklist: React.FC<{s: any; C: T}> = ({s, C}) => (
	<div style={{...PAGE(72)}}>
		<Label C={C}>{s.label || 'Before you submit'}</Label>
		<H C={C}>{s.title}</H>
		<Box C={C} fill="#fff" border={C.support} style={{marginTop: 30}}>
			{(s.items || []).map((t: string, k: number) => (
				<div key={k} style={{display: 'flex', gap: 24, alignItems: 'flex-start', marginTop: k ? 26 : 0}}>
					<span style={{width: 46, height: 46, border: `4px solid ${C.primary}`, borderRadius: 6, flexShrink: 0, marginTop: 2}} />
					<Body size={36}><Rich text={t} C={C} /></Body>
				</div>
			))}
		</Box>
	</div>
);

/** elements 30 and 26: glossary or revision list, with a mnemonic line */
const Glossary: React.FC<{s: any; C: T}> = ({s, C}) => (
	<div style={{...PAGE(72)}}>
		<Label C={C}>{s.label}</Label>
		<H C={C}>{s.title}</H>
		<div style={{marginTop: 20, border: `3px solid ${C.support}`, borderRadius: 8, overflow: 'hidden'}}>
			{(s.items || []).map((it: any, k: number) => (
				<div key={k} style={{display: 'flex', gap: 24, padding: '22px 26px', background: k % 2 ? C.soft : '#fff', borderTop: k ? `2px solid ${C.support}` : undefined}}>
					<span style={{fontFamily: F, fontWeight: 700, fontSize: 36, color: C.accentDeep, width: 56, flexShrink: 0}}>{String(it.n ?? k + 1).padStart(2, '0')}</span>
					<div>
						<div style={{fontFamily: F, fontWeight: 700, fontStyle: it.italic ? 'italic' : 'normal', fontSize: 32, color: C.primary}}>{it.head}</div>
						<Body size={30} color={INK} style={{marginTop: 4}}>{it.text}</Body>
					</div>
				</div>
			))}
		</div>
		{s.mnemonic ? (
			<Box C={C} rule={C.accent} style={{marginTop: 28}}>
				<Label C={C}>Remember it as</Label>
				<div style={{fontFamily: F, fontWeight: 700, fontSize: 40, color: C.primary, marginTop: 8}}>{s.mnemonic}</div>
			</Box>
		) : null}
	</div>
);

const Mcq: React.FC<{s: any; C: T; square?: boolean}> = ({s, C, square}) => (
	<div style={{...PAGE(64)}}>
		<div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
			<Label C={C}>{s.label}</Label>
			<Pills C={C} items={[s.tag]} />
		</div>
		<div style={{fontFamily: F, fontWeight: 700, fontSize: 32, lineHeight: 1.35, color: INK, marginTop: 18}}>{s.stem}</div>
		{(s.statements || []).map((t: string, k: number) => (
			<div key={k} style={{display: 'flex', gap: 14, marginTop: 12}}>
				<span style={{fontFamily: F, fontWeight: 700, fontSize: 28, color: C.accentDeep, width: 28, flexShrink: 0}}>{k + 1}.</span>
				<Body size={27} style={{lineHeight: 1.35}}>{t}</Body>
			</div>
		))}
		{s.ask ? <Body size={27} color={MUTED} style={{marginTop: 14}}>{s.ask}</Body> : null}
		<div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 16}}>
			{(s.options || []).map((o: string, k: number) => {
				const right = s.answer === k;
				return <div key={k} style={{borderRadius: 8, padding: '12px 18px', fontFamily: F, fontSize: 28, fontWeight: right ? 700 : 400,
					color: right ? '#1A1D22' : INK, background: right ? C.gain : C.soft, border: `3px solid ${right ? C.gain : C.support}`}}>({'abcd'[k]}) {o}</div>;
			})}
		</div>
		{s.explanation ? <Box C={C} rule={C.accent} style={{marginTop: 22, padding: '20px 24px'}}><Body size={28}>{s.explanation}</Body></Box> : null}
	</div>
);

/** element 31: practice tonight, the last slide, in the band colour */
const Practice: React.FC<{s: any; C: T}> = ({s, C}) => (
	<AbsoluteFill style={{background: band(C)}}>
		<svg width={300} height={300} style={{position: 'absolute', right: 60, top: 170, opacity: 0.55}}>
			{Array.from({length: 25}, (_, k) => <circle key={k} cx={30 + (k % 5) * 60} cy={30 + Math.floor(k / 5) * 60} r={6} fill={C.motif} />)}
		</svg>
		<div style={{position: 'absolute', left: 72, right: 72, top: 260}}>
			<Label C={C} color={C.accent}>Practice tonight</Label>
			<div style={{fontFamily: F, fontWeight: 700, fontSize: 78, lineHeight: 1.1, color: '#fff', marginTop: 16}}>
				{String(s.title).split(/(\*[^*]+\*)/).map((p, k) => p.startsWith('*') ? <span key={k} style={{color: C.accent}}>{p.slice(1, -1)}</span> : <span key={k}>{p}</span>)}
			</div>
			<div style={{marginTop: 44, background: '#fff', borderLeft: `12px solid ${C.accent}`, borderRadius: 6, padding: '30px 34px'}}>
				{(s.lines || []).map((l: string, k: number) => <Body key={k} size={36} style={{marginTop: k ? 18 : 0}}><Rich text={l} C={C} /></Body>)}
			</div>
			{s.pill ? <div style={{display: 'inline-block', marginTop: 44, background: C.accent, color: C.deep, borderRadius: 40, padding: '16px 34px',
				fontFamily: F, fontWeight: 700, fontSize: 32, letterSpacing: 2}}>{s.pill}</div> : null}
		</div>
	</AbsoluteFill>
);

/** a real page shown as it is (the sample brief), with one line under it */
const Picture: React.FC<{s: any; C: T}> = ({s, C}) => (
	<div style={{...PAGE(72)}}>
		<Label C={C}>{s.label}</Label>
		<div style={{marginTop: 18, height: 760, overflow: 'hidden', borderRadius: 8, border: `3px solid ${C.support}`, boxShadow: '0 16px 40px rgba(0,0,0,0.18)'}}>
			<Img src={staticFile(s.src)} style={{width: '100%', marginTop: s.offset || 0}} />
		</div>
		{s.caption ? <Box C={C} rule={C.accent} style={{marginTop: 26}}><Body size={34}><Rich text={s.caption} C={C} /></Body></Box> : null}
	</div>
);

const KINDS: Record<string, React.FC<{s: any; C: T; square?: boolean}>> = {
	cover: Cover, pipeline: Pipeline, question: Question, answer: Answer, mostwrite: MostWrite, ladder: Ladder, budget: Budget,
	card: Card, lens: Lens, opening: Opening, anchors: Anchors, mistake: Mistake, checklist: Checklist, glossary: Glossary, mcq: Mcq, practice: Practice, picture: Picture,
};

export const DeskCarousel: React.FC<{desk: keyof typeof THEMES; i: number; n: number; slide: any; issue?: string; date?: string; square?: boolean; handle?: string}> =
	({desk, i, n, slide, issue, date, square, handle}) => {
	const C = THEMES[desk] || THEMES.gs;
	F = desk === 'umbrella' ? POPPINS : ARIAL;
	const K = KINDS[slide.kind] || Anchors;
	const Hh = square ? 1080 : 1350;
	const dark = slide.kind === 'practice';
	return (
		<AbsoluteFill style={{background: '#FFFFFF', overflow: 'hidden'}}>
			<K s={slide} C={C} square={square} />
			{/* the band header, as on every page of the brief */}
			<div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 128, background: dark || slide.kind === 'cover' ? 'transparent' : band(C)}}>
				<div style={{position: 'absolute', left: 72, right: 72, top: 36, display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
					<span style={{fontFamily: F, fontWeight: 700, fontSize: 34, letterSpacing: 2, color: '#fff'}}>{C.name}</span>
					<span style={{fontFamily: F, fontWeight: 700, fontSize: 26, color: C.accent}}>{[issue ? `Issue #${issue}` : '', date].filter(Boolean).join('  |  ')}</span>
				</div>
				<div style={{position: 'absolute', left: 72, top: 84, fontFamily: F, fontWeight: 700, fontSize: 20, letterSpacing: 2, color: C.accent, textTransform: 'uppercase'}}>{C.tag}</div>
				{!dark && slide.kind !== 'cover' ? <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, height: 6, background: C.accent}} /> : null}
			</div>
			<div style={{position: 'absolute', left: 72, right: 72, top: Hh - 78, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
				<span style={{fontFamily: F, fontSize: 24, color: dark ? C.support : MUTED}}>{handle || '@upscdesk.official'}</span>
				{n > 1 ? (
					<div style={{display: 'flex', gap: 10, alignItems: 'center'}}>
						{i === 0 ? <span style={{fontFamily: F, fontWeight: 700, fontSize: 24, letterSpacing: 2, color: C.accentDeep, marginRight: 14}}>SWIPE</span> : null}
						{Array.from({length: n}, (_, k) => <span key={k} style={{width: k === i ? 36 : 12, height: 12, borderRadius: 6, background: k === i ? C.accent : dark ? C.motif : C.support}} />)}
					</div>
				) : null}
			</div>
		</AbsoluteFill>
	);
};
