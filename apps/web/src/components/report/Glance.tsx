import type { CardView, Rating } from "@/lib/types";
import { ratingPct, ratingText } from "@/lib/report";

function RatingValue({ r }: { r: Rating }) {
  return <>{r.rating}{(r.out_of ?? 5) !== 5 && <span className="of">/{r.out_of}</span>}</>;
}

export function Glance({ us, them, view }: { us: string; them: string; view: CardView }) {
  const { ratings, axis_lo: lo } = view;
  return (
    <div className="glance">
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
    </div>
  );
}
