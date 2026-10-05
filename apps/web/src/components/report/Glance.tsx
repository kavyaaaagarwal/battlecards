import type { CardView, Rating } from "@/lib/types";
import { ratingPct, ratingText } from "@/lib/report";

function RatingValue({ r }: { r: Rating }) {
  return <>{r.rating}{(r.out_of ?? 5) !== 5 && <span className="of">/{r.out_of}</span>}</>;
}

export function Glance({ us, them, view }: { us: string; them: string; view: CardView }) {
  const { tally, known, ratings, axis_lo: lo, evidence } = view;
  return (
    <div className="glance">
      <div>
        <div className="label">Capability scorecard</div>
        {known ? (<>
          <div className="big">{tally.lead}<small>of {known} we lead</small></div>
          <div className="stack" role="img" aria-label={`We lead ${tally.lead}, even ${tally.even}, they lead ${tally.behind}`}>
            {tally.lead > 0 && <span className="s-lead" style={{ flex: tally.lead }} data-tip={`We lead on ${tally.lead}`} />}
            {tally.even > 0 && <span className="s-even" style={{ flex: tally.even }} data-tip={`Even on ${tally.even}`} />}
            {tally.behind > 0 && <span className="s-behind" style={{ flex: tally.behind }} data-tip={`They lead on ${tally.behind}`} />}
          </div>
          <div className="keys">
            <span><span className="sw s-lead" />We lead <b>{tally.lead}</b></span>
            <span><span className="sw s-even" />Even <b>{tally.even}</b></span>
            <span><span className="sw s-behind" />They lead <b>{tally.behind}</b></span>
          </div>
        </>) : <div className="empty">Not enough evidence to compare capabilities.</div>}
      </div>
      <div>
        <div className="label">Review ratings</div>
        {ratings.length ? (<>
          <div className="legend"><span><span className="sw dot-us" />{us}</span><span><span className="sw dot-them" />{them}</span></div>
          <div className="rplot">
            {ratings.map((x) => {
              const pu = ratingPct(x.us, lo), pt = ratingPct(x.them, lo);
              const close = !!x.us && !!x.them && Math.abs(pu - pt) < 14;
              return (
                <div key={x.site} style={{ display: "contents" }}>
                  <div className="rsite">{x.site}</div>
                  <div className="rtrack">
                    {x.them && (<><span className="rdot them" style={{ left: `${pt}%` }} data-tip={`${them} on ${x.site}: ${ratingText(x.them)}`} />
                      <span className={`rval${close ? " below" : ""}`} style={{ left: `${pt}%` }}><RatingValue r={x.them} /></span></>)}
                    {x.us && (<><span className="rdot us" style={{ left: `${pu}%` }} data-tip={`${us} on ${x.site}: ${ratingText(x.us)}`} />
                      <span className="rval" style={{ left: `${pu}%` }}><RatingValue r={x.us} /></span></>)}
                  </div>
                </div>
              );
            })}
            <div className="raxis"><span>{lo}</span><span>5</span></div>
          </div>
        </>) : <div className="empty">No independent ratings found.</div>}
      </div>
      <div>
        <div className="label">Evidence quality</div>
        <div className="big">{`${evidence.pct}%`}<small>independent</small></div>
        <div className="meter" role="img" aria-label={`${evidence.pct} percent of citations independent`}><span style={{ width: `${evidence.pct}%` }} /></div>
        <div className="keys"><span>{evidence.independent} of {evidence.total} sources are reviews, forums, news or analysts - not vendor sites.</span></div>
      </div>
    </div>
  );
}
