import React from 'react';
import {AbsoluteFill, Audio, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont} from '@remotion/google-fonts/BarlowCondensed';
import {loadFont as loadHand} from '@remotion/google-fonts/Kalam';

/*
 * One Sociology or Essay Reel, 1080 x 1920, cut from the day's own script.
 *
 * The GS Short's grammar (things arrive on their spoken beat and stay; the mark moves) with
 * the long video's hand: a headline that types itself, a pipeline whose arrows draw, an
 * answer written out line by line on a ruled sheet, struck line by line in the examiner's
 * red, and rewritten. Each desk tells its own story:
 *
 *   sociology  news -> concept -> thinker, then the average opening struck and rewritten
 *              as sociology, and the mark moving from the band's floor to its top
 *   essay      the topic as set, the literal reading struck for the real one, the lenses
 *              fanning out from the topic, then a flat opening line rewritten
 *
 * Every time is a beat in seconds from the narration's own alignment (see ops/reel_cut.py).
 */
const {fontFamily: COND} = loadFont('normal', {weights: ['600', '700', '800'], subsets: ['latin']});
const {fontFamily: HAND} = loadHand('normal', {weights: ['400', '700'], subsets: ['latin']});
const SANS = "'Liberation Sans', Arial, Helvetica, sans-serif";

type Theme = {night: string; deep: string; panel: string; line: string; accent: string; accentDeep: string; cream: string; grey: string; label: string};
const THEMES: Record<string, Theme> = {
	// Steel and Amber, the Sociology Desk's own tokens
	sociology: {night: '#0C1A2E', deep: '#142038', panel: '#1B3050', line: '#3C587F', accent: '#F59E0B', accentDeep: '#B26E00',
		cream: '#EAF1FA', grey: '#8FA5C2', label: 'Sociology Optional'},
	// Claret and Gold, the Essay Desk's own tokens (the gold lifted a step so it reads on claret)
	essay: {night: '#23090F', deep: '#32121A', panel: '#4A1D27', line: '#78464E', accent: '#D4A53A', accentDeep: '#8A6300',
		cream: '#F6EFE3', grey: '#C3A7AC', label: 'UPSC Essay'},
};
const RED = '#D2493F', PAPER = '#FBF8F0', INK = '#1E2A3A', RULE = '#C9D6E6';

export type ReelProps = {beats: Record<string, number>; data: any; voice?: string; seconds?: number};

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const useT = () => {const f = useCurrentFrame(); const {fps} = useVideoConfig(); return f / fps;};

/* arrives on its beat with a short spring, and (optionally) leaves on another */
const Pop: React.FC<{at: number; until?: number; y?: number; children: React.ReactNode; style?: React.CSSProperties}> =
({at, until, y = 24, children, style}) => {
	const frame = useCurrentFrame(); const {fps} = useVideoConfig();
	const t = frame / fps;
	if (t < at) return null;
	const s = spring({frame: frame - at * fps, fps, config: {damping: 16, stiffness: 190, mass: 0.5}});
	const out = until === undefined ? 1 : interpolate(t, [until, until + 0.35], [1, 0], clamp);
	if (out <= 0) return null;
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
			<div style={{position: 'absolute', right: 70, top: 150, display: 'grid', gridTemplateColumns: 'repeat(5, 12px)', gap: 14, opacity: 0.55}}>
				{Array.from({length: 25}).map((_, i) => <span key={i} style={{width: 7, height: 7, borderRadius: 4, background: th.line}} />)}
			</div>
			{voice ? <Audio src={staticFile(voice)} /> : null}
			<div style={{position: 'absolute', left: 64, top: 74, display: 'flex', gap: 14, alignItems: 'center'}}>
				<span style={{fontFamily: COND, fontWeight: 800, fontSize: 36, letterSpacing: 5, color: th.cream}}>UPSC DESK</span>
				<span style={{width: 8, height: 8, borderRadius: 4, background: th.accent}} />
				<span style={{fontFamily: COND, fontWeight: 600, fontSize: 36, color: th.accent}}>{eyebrow}</span>
			</div>
			{/* progress, so a scroller knows how long is left */}
			<div style={{position: 'absolute', left: 64, right: 64, top: 128, height: 5, background: th.line + '66', borderRadius: 3}}>
				<div style={{width: `${Math.min(100, (t / seconds) * 100)}%`, height: '100%', background: th.accent, borderRadius: 3}} />
			</div>
		</>
	);
};

const Kicker: React.FC<{c: string; children: React.ReactNode}> = ({c, children}) => (
	<div style={{fontFamily: COND, fontWeight: 800, fontSize: 32, letterSpacing: 5, color: c}}>{children}</div>
);

/* the ruled sheet: lines written out one after another, then struck with margin notes */
const Sheet: React.FC<{th: Theme; title: string; score?: string; lines: {text: string; note?: string}[]; write: number; writeEnd: number;
	strike: number; gap: number; strikeAt?: number[]}> = ({th, title, score, lines, write, writeEnd, strike, gap, strikeAt}) => {
	const total = lines.reduce((a, l) => a + l.text.length, 0) || 1;
	let acc = 0;
	return (
		<div style={{background: PAPER, borderRadius: 16, padding: '20px 24px 22px 74px', position: 'relative', boxShadow: '0 22px 60px #00000070',
			backgroundImage: `repeating-linear-gradient(180deg, transparent 0 69px, ${RULE} 69px 71px)`, backgroundPosition: '0 62px'}}>
			{/* the red margin every answer booklet has */}
			<div style={{position: 'absolute', left: 50, top: 0, bottom: 0, width: 3, background: '#E7A3A0'}} />
			<div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6}}>
				<span style={{fontFamily: COND, fontWeight: 800, fontSize: 30, letterSpacing: 3, color: '#7A869A'}}>{title}</span>
				{score ? <span style={{fontFamily: HAND, fontWeight: 700, fontSize: 52, color: RED}}>{score}</span> : null}
			</div>
			{lines.map((l, i) => {
				const a = write + (writeEnd - write) * (acc / total);
				acc += l.text.length;
				const b = write + (writeEnd - write) * (acc / total);
				const at = strikeAt?.[i] ?? strike + i * gap;
				return (
					<div key={i} style={{display: 'grid', gridTemplateColumns: '1fr 200px', alignItems: 'center', minHeight: 70}}>
						<div style={{fontFamily: HAND, fontSize: 42, lineHeight: 1.6, whiteSpace: 'nowrap', overflow: 'visible'}}>
							<Struck at={at}><Typed text={l.text} from={a} to={b} color={INK} /></Struck>
						</div>
						<div style={{textAlign: 'right', transform: 'rotate(-4deg)'}}>
							{l.note ? (
								<Pop at={at + 0.3} y={8}>
									<span style={{fontFamily: HAND, fontWeight: 700, fontSize: 31, color: RED, whiteSpace: 'nowrap'}}>{l.note}</span>
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
const Rewrite: React.FC<{th: Theme; kicker: string; lines: string[]; at: number; gap: number; atList?: number[]}> = ({th, kicker, lines, at, gap, atList}) => (
	<div>
		<Pop at={at - 0.2}><Kicker c={th.accent}>{kicker}</Kicker></Pop>
		{lines.map((l, i) => {
			const a = atList?.[i] ?? at + i * gap;
			return (
				<Pop key={i} at={a} y={10}>
					<div style={{display: 'flex', alignItems: 'flex-start', gap: 14, marginTop: 16}}>
						<div style={{paddingTop: 18}}><RightArrow at={a} len={52} color={th.accent} /></div>
						<div style={{flex: 1, fontFamily: HAND, fontWeight: 700, fontSize: 46, lineHeight: 1.26, color: th.cream}}>
							<Typed text={l} from={a + 0.15} to={a + 0.15 + Math.min(1.8, l.length / 30)} color={th.cream} cursor={th.accent} />
						</div>
					</div>
				</Pop>
			);
		})}
	</div>
);

/* the mark moving from the band's floor to its top, with a bar */
const MarkJump: React.FC<{th: Theme; at: number; from: number; to: number; out: number; label: string}> = ({th, at, from, to, out, label}) => {
	const t = useT();
	const n = interpolate(t, [at, at + 1.0], [from, to], clamp);
	return (
		<Pop at={at}>
			<Kicker c={th.accent}>{label}</Kicker>
			<div style={{display: 'flex', alignItems: 'baseline', gap: 18, marginTop: 2}}>
				<span style={{fontFamily: COND, fontWeight: 800, fontSize: 120, color: th.grey, lineHeight: 0.85}}>
					<Struck at={at + 0.3}>{from}</Struck>
				</span>
				<span style={{fontFamily: COND, fontWeight: 800, fontSize: 80, color: th.accent}}>→</span>
				<span style={{fontFamily: COND, fontWeight: 800, fontSize: 200, color: th.accent, lineHeight: 0.85}}>{Math.round(n)}</span>
				<span style={{fontFamily: COND, fontWeight: 700, fontSize: 56, color: th.grey}}>/ {out}</span>
			</div>
			<div style={{height: 18, background: th.line + '88', borderRadius: 9, marginTop: 18, overflow: 'hidden'}}>
				<div style={{width: `${(n / out) * 100}%`, height: '100%', background: th.accent}} />
			</div>
		</Pop>
	);
};

const CTA: React.FC<{th: Theme; at: number; free?: number; line: string}> = ({th, at, free, line}) => (
	<div style={{position: 'absolute', left: 64, right: 110, top: 1120, textAlign: 'center'}}>
		<Pop at={at}>
			<div style={{display: 'inline-block', background: th.accent, color: th.night, fontFamily: COND, fontWeight: 800, fontSize: 38,
				letterSpacing: 4, padding: '6px 18px', borderRadius: 8}}>ANSWER EVALUATION</div>
			<div style={{fontFamily: COND, fontWeight: 800, fontSize: line.length > 40 ? 54 : 64, lineHeight: 1.04, color: th.cream, marginTop: 14}}>{line}</div>
			<div style={{display: 'inline-block', background: th.accent, color: th.night, fontFamily: COND, fontWeight: 800, fontSize: 52,
				padding: '12px 28px', borderRadius: 12, marginTop: 14}}>evaluate.upscdesk.com</div>
		</Pop>
		{free !== undefined ? <Pop at={free} y={6}><div style={{fontFamily: SANS, fontSize: 32, color: th.accent, marginTop: 12}}>Five free every month</div></Pop> : null}
	</div>
);

/* ---------------------------------------------------------------- Sociology */
const Sociology: React.FC<ReelProps & {th: Theme}> = ({beats: B, data: d, th}) => {
	const t = useT();
	const steps = [
		{k: 'THE NEWS', ...d.news, at: B.news},
		{k: 'THE CONCEPT', ...d.concept, at: B.concept},
		{k: 'THE THINKER', ...d.thinker, at: B.thinker},
	];
	return (
		<>
			{/* 1. the headline types itself, then the question the series asks */}
			<div style={{position: 'absolute', left: 64, right: 110, top: 230}}>
				<Pop at={B.hook} until={B.question}>
					<div style={{fontFamily: COND, fontWeight: 800, fontSize: 96, lineHeight: 1.0, color: th.cream}}>
						<Typed text={d.headline} from={B.hook} to={B.hook2 - 0.2} color={th.cream} cursor={th.accent} />
					</div>
				</Pop>
				<Pop at={B.hook2} until={B.question}>
					<div style={{fontFamily: COND, fontWeight: 800, fontSize: 96, color: th.accent, marginTop: 10}}>{d.hook2}</div>
				</Pop>
			</div>

			{/* 2. the desk's chain as a pipeline: news, then concept, then thinker */}
			<div style={{position: 'absolute', left: 64, right: 110, top: 590}}>
				{steps.map((s, i) => (
					<React.Fragment key={s.k}>
						{i > 0 ? <Pop at={s.at - 0.55} until={B.question}><DownArrow at={s.at - 0.55} len={84} color={th.accent} /></Pop> : null}
						<Pop at={s.at} until={B.question}>
							<div style={{background: i === 2 ? th.accent : th.panel, border: `2px solid ${th.accent}${i === 2 ? '' : '66'}`, borderRadius: 20, padding: '22px 28px'}}>
								<div style={{fontFamily: COND, fontWeight: 800, fontSize: 30, letterSpacing: 4, color: i === 2 ? th.night : th.accent}}>{s.k}</div>
								<div style={{fontFamily: COND, fontWeight: 800, fontSize: 70, lineHeight: 1.0, color: i === 2 ? th.night : th.cream, marginTop: 4}}>{s.title}</div>
								{s.sub ? <div style={{fontFamily: SANS, fontSize: 34, color: i === 2 ? th.night : th.grey, marginTop: 8}}>{s.sub}</div> : null}
							</div>
						</Pop>
					</React.Fragment>
				))}
			</div>

			{/* 3. the question, 4. the average opening written and struck, 5. rewritten as sociology */}
			<div style={{position: 'absolute', left: 64, right: 110, top: 190}}>
				<Pop at={B.question} until={B.jump}>
					<div style={{background: th.panel, border: `2px solid ${th.accent}55`, borderRadius: 18, padding: '18px 24px'}}>
						<div style={{fontFamily: COND, fontWeight: 800, fontSize: 30, letterSpacing: 3, color: th.accent}}>{d.tag}</div>
						<div style={{fontFamily: COND, fontWeight: 700, fontSize: 50, color: th.cream, lineHeight: 1.08, marginTop: 6}}>{d.question}</div>
						<Pop at={B.directive} y={8}>
							<span style={{display: 'inline-block', marginTop: 10, fontFamily: COND, fontWeight: 800, fontSize: 40, color: th.night, background: th.accent, padding: '2px 12px', borderRadius: 6}}>{d.directive}</span>
						</Pop>
					</div>
				</Pop>
				<Pop at={B.write - 0.3} until={B.jump} style={{marginTop: 28}}>
					<Sheet th={th} title="HOW MOST ASPIRANTS OPEN" score={`${d.from} / ${d.out}`} lines={d.average}
						write={B.write} writeEnd={B.strike - 0.6} strike={B.strike} gap={d.strikeGap || 1.1} strikeAt={d.strikeAt} />
				</Pop>
				<div style={{marginTop: 30}}>
					{t < B.jump + 0.35 ? <Rewrite th={th} kicker={d.fixKicker || 'WRITE IT AS SOCIOLOGY'} lines={d.better} at={B.fix} gap={d.fixGap || 1.6} atList={d.fixAt} /> : null}
				</div>
			</div>

			{/* 6. the mark moves, 7. the evaluator */}
			<div style={{position: 'absolute', left: 64, right: 110, top: 220}}>
				<MarkJump th={th} at={B.jump} from={d.from} to={d.to} out={d.out} label={d.jumpLabel || 'NAME THE CONCEPT, AND THE MARK MOVES'} />
				<Pop at={B.jump + 0.8}>
					<div style={{background: th.panel, border: `2px solid ${th.accent}55`, borderRadius: 18, padding: '18px 24px', marginTop: 34}}>
						<Kicker c={th.accent}>THE LINES THAT MOVED IT</Kicker>
						{(d.better || []).map((l: string, i: number) => (
							<div key={i} style={{fontFamily: HAND, fontWeight: 700, fontSize: 38, lineHeight: 1.25, color: th.cream, marginTop: 10}}>{l}</div>
						))}
					</div>
				</Pop>
			</div>
			<CTA th={th} at={B.cta} free={B.free} line={d.cta_line} />
		</>
	);
};

/* ---------------------------------------------------------------- Essay */
const Essay: React.FC<ReelProps & {th: Theme}> = ({beats: B, data: d, th}) => {
	const t = useT();
	const lenses: {title: string; sub?: string}[] = d.lenses || [];
	const lensAt = (i: number) => d.lensAt?.[i] ?? B.lenses + 0.4 + i * (d.lensGap || 0.9);
	const shown = lenses.filter((_, i) => t >= lensAt(i)).length;
	return (
		<>
			{/* 1. the topic as set, typed out in quotes */}
			<div style={{position: 'absolute', left: 64, right: 110, top: 200}}>
				<Pop at={B.hook} until={B.lenses}>
					<Kicker c={th.accent}>{d.kicker || 'THE TOPIC, AS SET'}</Kicker>
					<div style={{fontFamily: HAND, fontWeight: 700, fontSize: 64, lineHeight: 1.18, color: th.cream, marginTop: 10}}>
						<Typed text={`“${d.topic}”`} from={B.hook} to={B.hook2 - 0.3} color={th.cream} cursor={th.accent} />
					</div>
				</Pop>
				<Pop at={B.hook2} until={B.lenses}>
					<div style={{fontFamily: COND, fontWeight: 800, fontSize: 76, color: th.accent, marginTop: 14}}>{d.hook2}</div>
				</Pop>
			</div>

			{/* 2. decode: the literal reading struck, the real one arriving on an arrow */}
			<div style={{position: 'absolute', left: 64, right: 110, top: 900}}>
				<Pop at={B.literal} until={B.lenses}>
					<Kicker c={th.grey}>WHAT MOST READ</Kicker>
					<div style={{fontFamily: HAND, fontSize: 44, color: th.grey, lineHeight: 1.25, marginTop: 6}}>
						<Struck at={B.decode - 0.5}>{d.literal}</Struck>
					</div>
				</Pop>
				<Pop at={B.decode} until={B.lenses}>
					<div style={{marginTop: 18}}><DownArrow at={B.decode} len={64} color={th.accent} /></div>
					<Kicker c={th.accent}>WHAT IT ASKS</Kicker>
					<div style={{fontFamily: HAND, fontWeight: 700, fontSize: 50, color: th.cream, lineHeight: 1.22, marginTop: 6}}>
						<Typed text={d.decode} from={B.decode + 0.2} to={B.decode + 0.2 + Math.min(2.2, d.decode.length / 34)} color={th.cream} cursor={th.accent} />
					</div>
				</Pop>
			</div>

			{/* 3. the lenses fan out from the topic, and the count climbs */}
			<div style={{position: 'absolute', left: 64, right: 110, top: 190}}>
				<Pop at={B.lenses} until={B.open}>
					<div style={{display: 'flex', alignItems: 'baseline', justifyContent: 'space-between'}}>
						<Kicker c={th.accent}>AN ESSAY IS READ THROUGH LENSES</Kicker>
						<span style={{fontFamily: COND, fontWeight: 800, fontSize: 96, color: th.accent, lineHeight: 0.9}}>{Math.max(1, shown)}</span>
					</div>
					<div style={{background: th.accent, color: th.night, borderRadius: 18, padding: '18px 24px', marginTop: 14, textAlign: 'center',
						fontFamily: COND, fontWeight: 800, fontSize: 64, lineHeight: 1.02}}>{d.hub}</div>
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
			<div style={{position: 'absolute', left: 64, right: 110, top: 200}}>
				<Pop at={B.open - 0.3} until={B.cta - 0.2}>
					<Sheet th={th} title="THE OPENING MOST WRITE" lines={d.average} write={B.open} writeEnd={B.strike - 0.6} strike={B.strike} gap={d.strikeGap || 1.1} strikeAt={d.strikeAt} />
				</Pop>
				<div style={{marginTop: 26}}>
					{t < B.cta ? <Rewrite th={th} kicker={d.fixKicker || 'OPEN WITH A CLAIM'} lines={d.better} at={B.fix} gap={d.fixGap || 1.6} atList={d.fixAt} /> : null}
				</div>
			</div>
			{/* the end keeps the opening that works, above the offer */}
			<div style={{position: 'absolute', left: 64, right: 110, top: 240}}>
				<Pop at={B.cta}>
					<div style={{background: th.panel, border: `2px solid ${th.accent}55`, borderRadius: 18, padding: '20px 26px'}}>
						<Kicker c={th.accent}>{d.keepKicker || 'THE OPENING THAT WORKS'}</Kicker>
						{(d.better || []).map((l: string, i: number) => (
							<div key={i} style={{fontFamily: HAND, fontWeight: 700, fontSize: 44, lineHeight: 1.25, color: th.cream, marginTop: 12}}>{l}</div>
						))}
						{lenses.length ? <div style={{fontFamily: COND, fontWeight: 700, fontSize: 32, color: th.grey, marginTop: 16}}>then {lenses.length} lenses, one thesis</div> : null}
					</div>
				</Pop>
			</div>
			<CTA th={th} at={B.cta} free={B.free} line={d.cta_line} />
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
