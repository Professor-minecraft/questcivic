import DiamondSparkles from './DiamondSparkles';

function RankBadge({ rank }) {
  let cls;
  if (rank === 1) {
    // Rank 1 badge: diamond shape
    cls = 'lb-rank-diamond';
  } else if (rank === 2) {
    // Rank 2: silver rank badge
    cls = 'bg-slate-300 text-slate-800 ring-2 ring-slate-200 rounded-full';
  } else if (rank === 3) {
    // Rank 3: bronze rank badge
    cls = 'bg-amber-700 text-amber-100 ring-2 ring-amber-600 rounded-full';
  } else {
    // Rank 4+: normal style
    cls = 'bg-slate-100 text-slate-600 rounded-full';
  }

  return (
    <span
      className={`inline-flex items-center justify-center w-8 h-8 text-xs font-bold shrink-0 relative z-10 ${cls}`}
      aria-label={`Rank ${rank}`}
    >
      {rank}
    </span>
  );
}

function RankLabel({ rank }) {
  if (rank === 1) return <span className="text-xs font-bold ml-1 shrink-0">🥇</span>;
  if (rank === 2) return <span className="text-xs font-bold text-slate-600 ml-1 shrink-0">🥈</span>;
  if (rank === 3) return <span className="text-xs font-bold text-amber-900 ml-1 shrink-0">🥉</span>;
  return null;
}

export default function LeaderboardRow({ item }) {
  const isTop3 = item.rank <= 3;
  const isRank1 = item.rank === 1;
  const isRank2 = item.rank === 2;
  const isRank3 = item.rank === 3;

  // Choose style by entry's rank NUMBER (not by list position)
  let rowClass = '';
  let nameTextClass = 'text-slate-800';
  let xpTextClass = 'text-amber-700';

  if (isRank1) {
    // Diamond style for rank 1
    rowClass = 'lb-shine-diamond';
    nameTextClass = 'text-[#0b2545] font-bold';
    xpTextClass = 'text-[#0b2545]';
  } else if (isRank2) {
    // Silver shine style for rank 2
    rowClass = 'lb-row-silver';
    nameTextClass = 'text-slate-950 font-bold';
    xpTextClass = 'text-amber-900';
  } else if (isRank3) {
    // Bronze shine style for rank 3
    rowClass = 'lb-row-bronze';
    nameTextClass = 'text-stone-950 font-bold';
    xpTextClass = 'text-amber-950';
  } else {
    // Rank 4 and above: normal style
    if (item.is_me) {
      rowClass = 'bg-blue-50 border-2 border-blue-500 ring-2 ring-blue-100';
    } else {
      rowClass = 'bg-white border border-slate-200';
    }
  }

  // The "You" highlight must still show on rows that have an effect
  const youHighlightClass = item.is_me && isTop3 ? 'lb-row-you ring-2 ring-blue-400' : '';

  return (
    <div
      className={`rounded-xl px-4 py-3 flex items-center gap-3 shadow-xs transition-all relative overflow-hidden ${rowClass} ${youHighlightClass}`}
    >
      {/* Sparkles for Rank 1 */}
      {isRank1 && <DiamondSparkles />}

      {/* Rank Badge */}
      <RankBadge rank={item.rank} />

      {/* Name + Medal Emoji */}
      <div className="flex-1 min-w-0 relative z-10 flex items-center">
        <span
          title={item.name}
          className={`min-w-0 overflow-hidden text-ellipsis whitespace-nowrap block ${isTop3 ? 'font-bold' : 'font-semibold'} text-sm sm:text-base ${nameTextClass}`}
          style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
        >
          {item.name}
        </span>
        {isTop3 && <RankLabel rank={item.rank} />}
      </div>

      {/* XP */}
      <div className={`shrink-0 flex items-center space-x-1 text-sm font-bold relative z-10 ${xpTextClass}`}>
        <span className={isRank1 ? 'text-[#0b2545]' : 'text-amber-500'}>★</span>
        <span>{item.xp} XP</span>
      </div>

      {/* "You" badge */}
      {item.is_me && (
        <span className="shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-blue-600 text-white shadow-xs relative z-10">
          You
        </span>
      )}
    </div>
  );
}
