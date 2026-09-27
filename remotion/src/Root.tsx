import React from 'react';
import {Composition} from 'remotion';
import {DeskShort} from './DeskShort';

// The Essay Desk's daily Reel, 1080 x 1920. DeskShort.tsx is the same file as in the
// Sociology repo (msduggal01/sociology-sentinel-scheduler); data.desk = 'essay' picks the
// claret and gold theme and the Essay's own story. Its length comes from the narration.
export const Root: React.FC = () => (
	<Composition id="DeskShort" component={DeskShort} width={1080} height={1920} fps={30} durationInFrames={1200}
		defaultProps={{beats: {}, data: {}} as any}
		calculateMetadata={({props}) => ({durationInFrames: Math.round(((props as any)?.seconds || 40) * 30)})} />
);
