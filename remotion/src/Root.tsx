import React from 'react';
import {Composition} from 'remotion';
import {DeskShort} from './DeskShort';
import {DeskCarousel} from './DeskCarousel';

// The Essay Desk's daily Reel, 1080 x 1920. DeskShort.tsx began as the same file as in the
// Sociology repo (msduggal01/sociology-sentinel-scheduler); since 27 September this copy also
// has the safe zone, the highlight token and the Essay's claret sheet, and still renders the
// Sociology story unchanged in colour. data.desk = 'essay' picks the claret and gold theme
// and the Essay's own story. Its length comes from the narration.
export const Root: React.FC = () => (
	<>
	<Composition id="DeskShort" component={DeskShort} width={1080} height={1920} fps={30} durationInFrames={1200}
		defaultProps={{beats: {}, data: {}} as any}
		calculateMetadata={({props}) => ({durationInFrames: Math.round(((props as any)?.seconds || 40) * 30)})} />
	{/* the Instagram and Facebook carousel, one still per slide (ops/carousel_render.py): 4:5, and 1:1 cards */}
	<Composition id="DeskCarousel" component={DeskCarousel} width={1080} height={1350} fps={30} durationInFrames={1} defaultProps={{desk: 'essay', i: 0, n: 1, slide: {kind: 'cover'}} as any} />
	<Composition id="DeskCard" component={DeskCarousel} width={1080} height={1080} fps={30} durationInFrames={1} defaultProps={{desk: 'essay', i: 0, n: 1, square: true, slide: {kind: 'cover'}} as any} />
	</>
);
