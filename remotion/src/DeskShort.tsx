import React from 'react';
import {AbsoluteFill, Audio, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont} from '@remotion/google-fonts/BarlowCondensed';
import {loadFont as loadHand} from '@remotion/google-fonts/Handlee';
import {loadFont as loadMark} from '@remotion/google-fonts/Kalam';

/*
 * One Sociology or Essay Reel, 1080 x 1920, cut from the day's own script.
 *
 * The GS Short's grammar (things arrive on their spoken beat and stay; the mark moves) with
 * the long video's hand: a headline that types itself, a pipeline whose arrows draw, an
 * answer written out line by line on a ruled sheet, struck line by line in the examiner's
 * red, and rewritten. Each desk tells its own story:
 *
 *   sociology  news -> concept -> thinker, then the question as set, the average opening
 *              struck and rewritten as sociology, and the mark moving from the band's floor
 *              to its top
 *   essay      the topic as set, the literal reading struck for the real one, the lenses
 *              fanning out from the topic, then a flat opening line rewritten
 *
 * Every time is a beat in seconds from the narration's own alignment (see ops/reel_cut.py).
 *
 * Layout keeps to the phone's safe zone: nothing is written in the top SAFE_TOP or the bottom
 * 380 px of the 1080 x 1920 frame, where Instagram and YouTube lay their own buttons and
 * captions, and each scene sits in the middle of what is left instead of hugging the top.
 * Each scene has faded out before the next one arrives.
 *
 * The same file serves both desks and is kept identical in the Sociology and Essay repos.
 */
const {fontFamily: COND} = loadFont('normal', {weights: ['600', '700', '800'], subsets: ['latin']});
// the aspirant's lines (the opening on the sheet, the rewrite) in Handlee, the owner's reference hand
const {fontFamily: HAND} = loadHand('normal', {weights: ['400'], subsets: ['latin']});
// the examiner's red notes and score on the Sociology sheet stay in Kalam, as on its long video
const {fontFamily: KALAM} = loadMark('normal', {weights: ['400', '700'], subsets: ['latin']});
const SANS = "'Liberation Sans', Arial, Helvetica, sans-serif";

/* accent is the brand's own colour (the eyebrow, the progress, the hub, the offer); hi is the
 * highlight for what is gained or put in (the rewrite, the real reading, the lens count, the
 * mark that moves), the role lime plays on the other desks' videos. paper, ink, rule and
 * sheetTitle dress the ruled answer sheet; mark is the examiner's hand on it. */
type Theme = {night: string; deep: string; panel: string; line: string; accent: string; accentDeep: string; hi: string; cream: string; grey: string;
	paper: string; ink: string; rule: string; sheetTitle: string; label: string; badge: string; mark: string};
const THEMES: Record<string, Theme> = {
	// Steel and Amber, the Sociology Desk's own tokens (its highlight is its amber)
	sociology: {night: '#0C1A2E', deep: '#142038', panel: '#1B3050', line: '#3C587F', accent: '#F59E0B', accentDeep: '#B26E00', hi: '#F59E0B',
		cream: '#EAF1FA', grey: '#8FA5C2', paper: '#FBF8F0', ink: '#1E2A3A', rule: '#C9D6E6', sheetTitle: '#7A869A',
		label: 'Sociology Optional', badge: 'ANSWER EVALUATION', mark: KALAM},
	// Claret and Gold, the Essay Desk's own tokens. The darks are claret #7A2D3A taken down
	// towards black (75, 60 and 30 per cent) and its line is claret lifted towards white, so
	// the frame reads as claret, not as a brown; the gold stays the owner's, lifted a step so
	// it reads on claret; the highlight is a citrus orange, the Essay's answer to lime. The
	// sheet is parchment with claret-black ink and rose rules, not Sociology's navy and steel.
	essay: {night: '#1F0B0F', deep: '#311217', panel: '#552029', line: '#A26C75', accent: '#D4A53A', accentDeep: '#8A6300', hi: '#FF9F1C',
		cream: '#F6EFE3', grey: '#D0B5BA', paper: '#FBF6EC', ink: '#2A1419', rule: '#E6CCC4', sheetTitle: '#9A6B74',
		label: 'UPSC Essay', badge: 'ESSAY EVALUATION', mark: HAND},
};
const RED = '#D2493F';
const SAFE_TOP = 236;              // the brand line sits here; every scene starts below 330
const SAFE_BOTTOM = 1920 - 380;    // nothing is written below this
const ZONE_TOP = 330;
const MID = (ZONE_TOP + SAFE_BOTTOM) / 2;
// a scene has faded out (0.35 s) before the next one arrives
const OUT = 0.4;

export type ReelProps = {beats: Record<string, number>; data: any; voice?: string; seconds?: number};

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const useT = () => {const f = useCurrentFrame(); const {fps} = useVideoConfig(); return f / fps;};

/* arrives on its beat with a short spring, and (optionally) leaves on another. With `keep` it
   holds its place while unseen, so a block centred on the screen does not move as its parts arrive */
const Pop: React.FC<{at: number; until?: number; y?: number; children: React.ReactNode; style?: React.CSSProperties; keep?: boolean}> =
({at, until, y = 24, children, style, keep}) => {
	const frame = useCurrentFrame(); const {fps} = useVideoConfig();
	const t = frame / fps;
	const hidden = keep ? <div style={{...style, visibility: 'hidden'}}>{children}</div> : null;
	if (t < at) return hidden;
	const s = spring({frame: frame - at * fps, fps, config: {damping: 16, stiffness: 190, mass: 0.5}});
	const out = until === undefined ? 1 : interpolate(t, [until, until + 0.35], [1, 0], clamp);
	if (out <= 0) return hidden;
	return <div style={{...style, opacity: Math.min(1, s * 1.4) * out, transform: `translateY(${(1 - s) * y}px)`}}>{children}</div>;
};

/* types itself out between two beats; the untyped part is kept (invisible) so lines never re-wrap */
const Typed: React.FC<{text: string; from: number; to: number; color: string; cursor?: string}> = ({text, from, to, color, cursor}) => {
	const t = useT();
	const n = Math.round(interpolate(t, [from, to], [0, text.length], clamp));
	const typing = t >= from && n < text.length;
	const blink = Math.floor(t * 2.4) % 2 === 0;
	return (
		<span>
			<span style={{color}}>{text.slice(0, n)}</span>
			{typing || (t >= to && t < to + 0.8 && blink) ? <span style={{color: cursor || color, opacity: 0.9}}>|</span> : null}
			<span style={{color: 'transparent'}}>{text.slice(n)}</span>
		</span>
	);
};

/* a red pen stroke drawn left to right across whatever it wraps */
const Struck: React.FC<{at: number; children: React.ReactNode}> = ({at, children}) => {
	const t = useT();
	const p = interpolate(t, [at, at + 0.45], [0, 1], clamp);
	return (
		<span style={{position: 'relative', display: 'inline-block'}}>
			{children}
			{p > 0 ? <span style={{position: 'absolute', left: -4, top: '54%', height: 5, width: `calc(${p * 100}% + 8px)`, background: RED,
				borderRadius: 3, transform: 'rotate(-0.8deg)', boxShadow: '0 1px 0 #00000022'}} /> : null}
		</span>
	);
};

/* a vertical arrow that draws down from its tail, head riding the tip */
const DownArrow: React.FC<{at: number; len: number; color: string}> = ({at, len, color}) => {
	const t = useT();
	const p = interpolate(t, [at, at + 0.5], [0, 1], clamp);
	if (p <= 0) return <div style={{height: len}} />;
	const h = Math.max(0, len * p - 18);
	return (
		<div style={{height: len, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
			<div style={{width: 6, height: h, background: color, borderRadius: 3}} />
			<div style={{width: 0, height: 0, borderLeft: '16px solid transparent', borderRight: '16px solid transparent', borderTop: `20px solid ${color}`}} />
		</div>
	);
};

/* a horizontal arrow that draws right, for swaps */
const RightArrow: React.FC<{at: number; len: number; color: string}> = ({at, len, color}) => {
	const t = useT();
	const p = interpolate(t, [at, at + 0.4], [0, 1], clamp);
	return (
		<div style={{width: len, display: 'flex', alignItems: 'center', opacity: p > 0 ? 1 : 0}}>
			<div style={{height: 6, width: Math.max(0, len * p - 18), background: color, borderRadius: 3}} />
			<div style={{width: 0, height: 0, borderTop: '14px solid transparent', borderBottom: '14px solid transparent', borderLeft: `20px solid ${color}`}} />
		</div>
	);
};

const Chrome: React.FC<{th: Theme; voice?: string; eyebrow: string; seconds: number}> = ({th, voice, eyebrow, seconds}) => {
	const t = useT();
	return (
		<>
			<AbsoluteFill style={{background: `radial-gradient(120% 70% at 30% 18%, ${th.panel} 0%, ${th.deep} 45%, ${th.night} 100%)`}} />
			{/* the brand's dot grid, top right */}
			<div style={{position: 'absolute', right: 70, top: SAFE_TOP, display: 'grid', gridTemplateColumns: 'repeat(5, 12px)', gap: 14, opacity: 0.55}}>
				{Array.from({length: 25}).map((_, i) => <span key={i} style={{width: 7, height: 7, borderRadius: 4, background: th.line}} />)}
			</div>
			{voice ? <Audio src={staticFile(voice)} /> : null}
			<div style={{position: 'absolute', left: 64, top: SAFE_TOP, display: 'flex', gap: 14, alignItems: 'center'}}>
				<span style={{fontFamily: COND, fontWeight: 800, fontSize: 36, letterSpacing: 5, color: th.cream}}>UPSC DESK</span>
				<span style={{width: 8, height: 8, borderRadius: 4, background: th.accent}} />
				<span style={{fontFamily: COND, fontWeight: 600, fontSize: 36, color: th.accent}}>{eyebrow}</span>
			</div>
			{/* progress, so a scroller knows how long is left */}
			<div style={{position: 'absolute', left: 64, right: 170, top: SAFE_TOP + 54, height: 5, background: th.line + '66', borderRadius: 3}}>
				<div style={{width: `${Math.min(100, (t / seconds) * 100)}%`, height: '100%', background: th.accent, borderRadius: 3}} />
			</div>
		</>
	);
};

/* one scene, centred between ZONE_TOP and SAFE_BOTTOM (and clear of the buttons on the right);
   with `until` the whole scene fades out together, finished before the next scene arrives */
const Zone: React.FC<{until?: number; children: React.ReactNode}> = ({until, children}) => {
	const t = useT();
	const out = until === undefined ? 1 : interpolate(t, [until, until + 0.35], [1, 0], clamp);
	if (out <= 0) return null;
	return (
		<div style={{position: 'absolute', left: 64, right: 110, top: ZONE_TOP, bottom: 1920 - SAFE_BOTTOM, display: 'flex', flexDirection: 'column',
			justifyContent: 'center', opacity: out}}>
			{children}
		</div>
	);
};

const Kicker: React.FC<{c: string; children: React.ReactNode}> = ({c, children}) => (
	<div style={{fontFamily: COND, fontWeight: 800, fontSize: 32, letterSpacing: 5, color: c}}>{children}</div>
);

/* the ruled sheet: lines written out one after another, then struck with margin notes. A line
   over 30 characters is set smaller (to the width of 27 at full size) so it keeps clear of its
   margin note; a note over 14 is set smaller too, and the margin column holds its 200 px
   however long the line beside it, so a note stays on the paper. */
const Sheet: React.FC<{th: Theme; title: string; score?: string; lines: {text: string; note?: string}[]; write: number; writeEnd: number;
	strike: number; gap: number; strikeAt?: number[]}> = ({th, title, score, lines, write, writeEnd, strike, gap, strikeAt}) => {
	const total = lines.reduce((a, l) => a + l.text.length, 0) || 1;
	let acc = 0;
	return (
		<div style={{background: th.paper, borderRadius: 16, padding: '20px 24px 22px 74px', position: 'relative', boxShadow: '0 22px 60px #00000070',
			backgroundImage: `repeating-linear-gradient(180deg, transparent 0 69px, ${th.rule} 69px 71px)`, backgroundPosition: '0 62px'}}>
			{/* the red margin every answer booklet has */}
			<div style={{position: 'absolute', left: 50, top: 0, bottom: 0, width: 3, background: '#E7A3A0'}} />
			<div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6}}>
				<span style={{fontFamily: COND, fontWeight: 800, fontSize: 30, letterSpacing: 3, color: th.sheetTitle}}>{title}</span>
				{score ? <span style={{fontFamily: th.mark, fontWeight: 700, fontSize: 52, color: RED}}>{score}</span> : null}
			</div>
			{lines.map((l, i) => {
				const a = write + (writeEnd - write) * (acc / total);
				acc += l.text.length;
				const b = write + (writeEnd - write) * (acc / total);
				const at = strikeAt?.[i] ?? strike + i * gap;
				return (
					<div key={i} style={{display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 200px', alignItems: 'center', minHeight: 70}}>
						<div style={{fontFamily: HAND, fontSize: l.text.length > 30 ? Math.round(42 * 27 / l.text.length) : 42, lineHeight: 1.6, whiteSpace: 'nowrap', overflow: 'visible'}}>
							<Struck at={at}><Typed text={l.text} from={a} to={b} color={th.ink} /></Struck>
						</div>
						<div style={{display: 'flex', justifyContent: 'flex-end', transform: 'rotate(-4deg)'}}>
							{l.note ? (
								<Pop at={at + 0.3} y={8}>
									<span style={{fontFamily: th.mark, fontWeight: 700, fontSize: l.note.length > 14 ? Math.floor(31 * 12 / l.note.length) : 31, color: RED, whiteSpace: 'nowrap'}}>{l.note}</span>
								</Pop>
							) : null}
						</div>
					</div>
				);
			})}
		</div>
	);
};

/* the lines that replace the struck ones, each arriving with an arrow */
const Rewrite: React.FC<{th: Theme; kicker: string; lines: string[]; at: number; gap: number; atList?: number[]; keep?: boolean}> = ({th, kicker, lines, at, gap, atList, keep}) => (
	<div>
		<Pop at={at - 0.2} keep={keep}><Kicker c={th.hi}>{kicker}</Kicker></Pop>
		{lines.map((l, i) => {
			const a = atList?.[i] ?? at + i * gap;
			return (
				<Pop key={i} at={a} y={10} keep={keep}>
					<div style={{display: 'flex', alignItems: 'flex-start', gap: 14, marginTop: 16}}>
						<div style={{paddingTop: 18}}><RightArrow at={a} len={52} color={th.hi} /></div>
						<div style={{flex: 1, fontFamily: HAND, fontWeight: 700, fontSize: 46, lineHeight: 1.26, color: th.cream}}>
							<Typed text={l} from={a + 0.15} to={a + 0.15 + Math.min(1.8, l.length / 30)} color={th.cream} cursor={th.hi} />
						</div>
					</div>
				</Pop>
			);
		})}
	</div>
);

/* the mark moving from the band's floor to its top, with a bar */
const MarkJump: React.FC<{th: Theme; at: number; from: number; to: number; out: number; label: string; keep?: boolean}> = ({th, at, from, to, out, label, keep}) => {
	const t = useT();
	const n = interpolate(t, [at, at + 1.0], [from, to], clamp);
	return (
		<Pop at={at} keep={keep}>
			<Kicker c={th.accent}>{label}</Kicker>
			<div style={{display: 'flex', alignItems: 'baseline', gap: 18, marginTop: 2}}>
				<span style={{fontFamily: COND, fontWeight: 800, fontSize: 120, color: th.grey, lineHeight: 0.85}}>
					<Struck at={at + 0.3}>{from}</Struck>
				</span>
				<span style={{fontFamily: COND, fontWeight: 800, fontSize: 80, color: th.hi}}>→</span>
				<span style={{fontFamily: COND, fontWeight: 800, fontSize: 200, color: th.hi, lineHeight: 0.85}}>{Math.round(n)}</span>
				<span style={{fontFamily: COND, fontWeight: 700, fontSize: 56, color: th.grey}}>/ {out}</span>
			</div>
			<div style={{height: 18, background: th.line + '88', borderRadius: 9, marginTop: 18, overflow: 'hidden'}}>
				<div style={{width: `${(n / out) * 100}%`, height: '100%', background: th.hi}} />
			</div>
		</Pop>
	);
};

/* the offer: placed at `top`, or (inline) in a centred scene, holding its place until it arrives */
const CTA: React.FC<{th: Theme; at: number; free?: number; line: string; top?: number; badge?: string; inline?: boolean}> = ({th, at, free, line, top = 1120, badge, inline}) => (
	<div style={inline ? {textAlign: 'center', marginTop: 56} : {position: 'absolute', left: 64, right: 110, top, textAlign: 'center'}}>
		<Pop at={at} keep={inline}>
			<div style={{display: 'inline-block', background: th.accent, color: th.night, fontFamily: COND, fontWeight: 800, fontSize: 38,
				letterSpacing: 4, padding: '6px 18px', borderRadius: 8}}>{badge || th.badge}</div>
			<div style={{fontFamily: COND, fontWeight: 800, fontSize: line.length > 40 ? 54 : 64, lineHeight: 1.04, color: th.cream, marginTop: 14}}>{line}</div>
			<div style={{display: 'inline-block', background: th.accent, color: th.night, fontFamily: COND, fontWeight: 800, fontSize: 52,
				padding: '12px 28px', borderRadius: 12, marginTop: 14}}>evaluate.upscdesk.com</div>
		</Pop>
		{free !== undefined ? <Pop at={free} y={6} keep={inline}><div style={{fontFamily: SANS, fontSize: 32, color: th.accent, marginTop: 12}}>Five free every month</div></Pop> : null}
	</div>
);

/* ---------------------------------------------------------------- Sociology */
/* the question exactly as set, its directive lit in place when the voice says it; a long
   question is set smaller so the sheet and the rewrite still fit under it */
const Question: React.FC<{th: Theme; q: string; directive: string; at: number}> = ({th, q, directive, at}) => {
	const t = useT();
	const k = directive ? q.toLowerCase().indexOf(directive.toLowerCase()) : -1;
	const lit = interpolate(t, [at, at + 0.35], [0, 1], clamp);
	const size = q.length <= 140 ? 50 : q.length <= 220 ? 44 : q.length <= 300 ? 40 : 36;
	return (
		<div style={{fontFamily: COND, fontWeight: 700, fontSize: size, color: th.cream, lineHeight: 1.08, marginTop: 6}}>
			{k < 0 ? q : (
				<>
					{q.slice(0, k)}
					<span style={{background: lit > 0 ? th.accent : 'transparent', color: lit > 0.5 ? th.night : th.cream, borderRadius: 6, padding: '0 6px',
						boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone'}}>{q.slice(k, k + directive.length)}</span>
					{q.slice(k + directive.length)}
				</>
			)}
		</div>
	);
};

// a line of the chain holds its one line: a title over 26 characters, a headline over 40 or
// a sub over 46 is set smaller rather than wrapped, so the whole chain stays in the safe zone
const fit = (s: string | undefined, size: number, chars: number, min: number) => {
	const n = (s || '').length;
	return n > chars ? Math.max(min, Math.floor(size * chars / n)) : size;
};
// the same for a block that wraps over several lines: its area, not its width, is kept
const fitArea = (s: string | undefined, size: number, chars: number, min: number) => {
	const n = (s || '').length;
	return n > chars ? Math.max(min, Math.floor(size * Math.sqrt(chars / n))) : size;
};

const Sociology: React.FC<ReelProps & {th: Theme}> = ({beats: B, data: d, th}) => {
	const t = useT();
	const steps = [
		{k: 'THE NEWS', ...d.news, at: B.news},
		{k: 'THE CONCEPT', ...d.concept, at: B.concept},
		{k: 'THE THINKER', ...d.thinker, at: B.thinker},
	];
	// each scene has left (its fade finished) before the next one arrives
	const hookOut = B.question - OUT, sheetOut = B.jump - OUT;
	const head = fit(d.headline, 96, 40, 80);
	return (
		<>
			{/* 1. the headline types itself, then the question the series asks, 2. the desk's chain as a pipeline: news, concept, thinker */}
			{t < hookOut + 0.35 ? (
				<Zone until={hookOut}>
					<Pop at={B.hook} keep>
						<div style={{fontFamily: COND, fontWeight: 800, fontSize: head, lineHeight: 1.0, color: th.cream}}>
							<Typed text={d.headline} from={B.hook} to={B.hook2 - 0.2} color={th.cream} cursor={th.accent} />
						</div>
					</Pop>
					<Pop at={B.hook2} keep>
						<div style={{fontFamily: COND, fontWeight: 800, fontSize: 96, color: th.accent, marginTop: 10}}>{d.hook2}</div>
					</Pop>
					<div style={{marginTop: 44}}>
						{steps.map((s, i) => (
							<React.Fragment key={s.k}>
								{i > 0 ? <Pop at={s.at - 0.55} keep><DownArrow at={s.at - 0.55} len={84} color={th.accent} /></Pop> : null}
								<Pop at={s.at} keep>
									<div style={{background: i === 2 ? th.accent : th.panel, border: `2px solid ${th.accent}${i === 2 ? '' : '66'}`, borderRadius: 20, padding: '22px 28px'}}>
										<div style={{fontFamily: COND, fontWeight: 800, fontSize: 30, letterSpacing: 4, color: i === 2 ? th.night : th.accent}}>{s.k}</div>
										<div style={{fontFamily: COND, fontWeight: 800, fontSize: fit(s.title, 70, 26, 50), lineHeight: 1.0, color: i === 2 ? th.night : th.cream, marginTop: 4}}>{s.title}</div>
										{s.sub ? <div style={{fontFamily: SANS, fontSize: fit(s.sub, 34, 46, 28), color: i === 2 ? th.night : th.grey, marginTop: 8}}>{s.sub}</div> : null}
									</div>
								</Pop>
							</React.Fragment>
						))}
					</div>
				</Zone>
			) : null}

			{/* 3. the question as set, 4. the average opening written and struck, 5. rewritten as sociology */}
			{t >= hookOut + 0.35 && t < sheetOut + 0.35 ? (
				<Zone until={sheetOut}>
					<Pop at={B.question} keep>
						<div style={{background: th.panel, border: `2px solid ${th.accent}55`, borderRadius: 18, padding: '18px 24px'}}>
							<div style={{fontFamily: COND, fontWeight: 800, fontSize: 30, letterSpacing: 3, color: th.accent}}>{d.tag}</div>
							<Question th={th} q={d.question} directive={d.directive} at={B.directive} />
						</div>
					</Pop>
					<Pop at={B.write - 0.3} style={{marginTop: 28}} keep>
						<Sheet th={th} title="HOW MOST ASPIRANTS OPEN" score={`${d.from} / ${d.out}`} lines={d.average}
							write={B.write} writeEnd={B.strike - 0.6} strike={B.strike} gap={d.strikeGap || 1.1} strikeAt={d.strikeAt} />
					</Pop>
					<div style={{marginTop: 30}}>
						<Rewrite th={th} kicker={d.fixKicker || 'WRITE IT AS SOCIOLOGY'} lines={d.better} at={B.fix} gap={d.fixGap || 1.6} atList={d.fixAt} keep />
					</div>
				</Zone>
			) : null}

			{/* 6. the mark moves, the lines that moved it, 7. the evaluator */}
			{t >= sheetOut + 0.35 ? (
				<Zone>
					<MarkJump th={th} at={B.jump} from={d.from} to={d.to} out={d.out} label={d.jumpLabel || 'NAME THE CONCEPT, AND THE MARK MOVES'} keep />
					<Pop at={B.jump + 0.8} keep>
						<div style={{background: th.panel, border: `2px solid ${th.accent}55`, borderRadius: 18, padding: '18px 24px', marginTop: 34}}>
							<Kicker c={th.accent}>THE LINES THAT MOVED IT</Kicker>
							{(d.better || []).map((l: string, i: number) => (
								<div key={i} style={{fontFamily: HAND, fontWeight: 700, fontSize: 38, lineHeight: 1.25, color: th.cream, marginTop: 10}}>{l}</div>
							))}
						</div>
					</Pop>
					<CTA th={th} at={B.cta} free={B.free} line={d.cta_line} badge={d.badge} inline />
				</Zone>
			) : null}
		</>
	);
};

/* ---------------------------------------------------------------- Essay */
// Heights the scenes are centred on, from the type sizes below: a lens row is 136 px, the
// lens header and hub 210; the sheet with its rewrite about 700.
const lensTop = (n: number) => Math.max(340, Math.round(MID - (210 + n * 136) / 2));
// a long field is set smaller rather than run past its room (fit and fitArea, above): a topic
// over 85 characters keeps the area of five lines, clear of the reading below it; the literal
// reading over 42 keeps its one struck line; a hub over 30 is narrowed so the lens list stays
// in the safe zone. Every field at or under those lengths is set as before.

const Essay: React.FC<ReelProps & {th: Theme}> = ({beats: B, data: d, th}) => {
	const t = useT();
	const lenses: {title: string; sub?: string}[] = d.lenses || [];
	const lensAt = (i: number) => d.lensAt?.[i] ?? B.lenses + 0.4 + i * (d.lensGap || 0.9);
	const shown = lenses.filter((_, i) => t >= lensAt(i)).length;
	// each scene has left (its fade finished) before the next one arrives, so no two are ever
	// on screen together; the sheet used to slide over the lens list at the change
	return (
		<>
			{/* 1. the topic as set, typed out in quotes */}
			<div style={{position: 'absolute', left: 64, right: 110, top: 430}}>
				<Pop at={B.hook} until={B.lenses - OUT}>
					<Kicker c={th.accent}>{d.kicker || 'THE TOPIC, AS SET'}</Kicker>
					<div style={{fontFamily: HAND, fontWeight: 700, fontSize: fitArea(d.topic, 64, 85, 40), lineHeight: 1.18, color: th.cream, marginTop: 10}}>
						<Typed text={`“${d.topic}”`} from={B.hook} to={B.hook2 - 0.3} color={th.cream} cursor={th.accent} />
					</div>
				</Pop>
				<Pop at={B.hook2} until={B.lenses - OUT}>
					<div style={{fontFamily: COND, fontWeight: 800, fontSize: 76, color: th.accent, marginTop: 14}}>{d.hook2}</div>
				</Pop>
			</div>

			{/* 2. decode: the literal reading struck, the real one arriving on an arrow */}
			<div style={{position: 'absolute', left: 64, right: 110, top: 990}}>
				<Pop at={B.literal} until={B.lenses - OUT}>
					<Kicker c={th.grey}>WHAT MOST READ</Kicker>
					<div style={{fontFamily: HAND, fontSize: fit(d.literal, 44, 42, 32), color: th.grey, lineHeight: 1.25, marginTop: 6}}>
						<Struck at={B.decode - 0.5}>{d.literal}</Struck>
					</div>
				</Pop>
				<Pop at={B.decode} until={B.lenses - OUT}>
					<div style={{marginTop: 18}}><DownArrow at={B.decode} len={64} color={th.hi} /></div>
					<Kicker c={th.hi}>WHAT IT ASKS</Kicker>
					<div style={{fontFamily: HAND, fontWeight: 700, fontSize: 50, color: th.cream, lineHeight: 1.22, marginTop: 6}}>
						<Typed text={d.decode} from={B.decode + 0.2} to={B.decode + 0.2 + Math.min(2.2, d.decode.length / 34)} color={th.cream} cursor={th.hi} />
					</div>
				</Pop>
			</div>

			{/* 3. the lenses fan out from the topic, and the count climbs */}
			<div style={{position: 'absolute', left: 64, right: 110, top: lensTop(lenses.length)}}>
				<Pop at={B.lenses} until={B.open - OUT}>
					<div style={{display: 'flex', alignItems: 'baseline', justifyContent: 'space-between'}}>
						<Kicker c={th.accent}>AN ESSAY IS READ THROUGH LENSES</Kicker>
						<span style={{fontFamily: COND, fontWeight: 800, fontSize: 96, color: th.hi, lineHeight: 0.9}}>{Math.max(1, shown)}</span>
					</div>
					<div style={{background: th.accent, color: th.night, borderRadius: 18, padding: '18px 24px', marginTop: 14, textAlign: 'center',
						fontFamily: COND, fontWeight: 800, fontSize: fit(d.hub, 64, 30, 50), lineHeight: 1.02}}>{d.hub}</div>
					{lenses.map((l, i) => {
						const at = lensAt(i);
						return (
							<div key={i} style={{display: 'flex', alignItems: 'center', gap: 16, marginTop: 18}}>
								<div style={{width: 60, display: 'flex', justifyContent: 'center'}}><Pop at={at - 0.1}><DownArrow at={at - 0.1} len={60} color={th.accent} /></Pop></div>
								<Pop at={at} y={12} style={{flex: 1}}>
									<div style={{background: th.panel, border: `2px solid ${th.accent}55`, borderRadius: 16, padding: '14px 22px'}}>
										<div style={{fontFamily: COND, fontWeight: 800, fontSize: 52, lineHeight: 1.0, color: th.cream}}>{l.title}</div>
										{l.sub ? <div style={{fontFamily: SANS, fontSize: 30, color: th.grey, marginTop: 4}}>{l.sub}</div> : null}
									</div>
								</Pop>
							</div>
						);
					})}
				</Pop>
			</div>

			{/* 4. the flat opening written and struck, 5. rewritten */}
			<div style={{position: 'absolute', left: 64, right: 110, top: 520}}>
				<Pop at={B.open} until={B.cta - OUT}>
					<Sheet th={th} title="THE OPENING MOST WRITE" lines={d.average} write={B.open} writeEnd={B.strike - 0.6} strike={B.strike} gap={d.strikeGap || 1.1} strikeAt={d.strikeAt} />
				</Pop>
				<div style={{marginTop: 26}}>
					{t < B.cta - 0.05 ? <Rewrite th={th} kicker={d.fixKicker || 'OPEN WITH A CLAIM'} lines={d.better} at={B.fix} gap={d.fixGap || 1.6} atList={d.fixAt} /> : null}
				</div>
			</div>
			{/* the end keeps the opening that works, above the offer */}
			<div style={{position: 'absolute', left: 64, right: 110, top: 430}}>
				<Pop at={B.cta}>
					<div style={{background: th.panel, border: `2px solid ${th.hi}66`, borderRadius: 18, padding: '20px 26px'}}>
						<Kicker c={th.hi}>{d.keepKicker || 'THE OPENING THAT WORKS'}</Kicker>
						{(d.better || []).map((l: string, i: number) => (
							<div key={i} style={{fontFamily: HAND, fontWeight: 700, fontSize: 44, lineHeight: 1.25, color: th.cream, marginTop: 12}}>{l}</div>
						))}
						{lenses.length ? <div style={{fontFamily: COND, fontWeight: 700, fontSize: 32, color: th.grey, marginTop: 16}}>then {lenses.length} lenses, one thesis</div> : null}
					</div>
				</Pop>
			</div>
			<CTA th={th} at={B.cta} free={B.free} line={d.cta_line} top={1010} badge={d.badge} />
		</>
	);
};

export const DeskShort: React.FC<ReelProps> = (p) => {
	const th = THEMES[p.data?.desk] || THEMES.sociology;
	const seconds = p.seconds || 40;
	return (
		<AbsoluteFill style={{background: th.night}}>
			<Chrome th={th} voice={p.voice} eyebrow={p.data?.eyebrow || th.label} seconds={seconds} />
			{p.data?.desk === 'essay' ? <Essay {...p} th={th} /> : <Sociology {...p} th={th} />}
		</AbsoluteFill>
	);
};
