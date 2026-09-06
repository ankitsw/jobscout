export default function CompanyTooltip({ name, profile, position }) {
  if (!name) return null;

  let body;
  if (profile === undefined) {
    body = <div className="tt-loading">Looking up company info&hellip;</div>;
  } else if (!profile) {
    body = <div className="tt-loading">No additional company info found.</div>;
  } else {
    const facts = [
      ['Industry', profile.classification],
      ['Size', profile.size],
      ['Founded', profile.founded],
      ['HQ', profile.headquarters],
    ].filter(([, value]) => value);

    const hasAnything = facts.length || profile.description || (profile.tech_stack || []).length
      || profile.ambitionbox_rating != null;

    if (!hasAnything) {
      body = <div className="tt-loading">No additional company info found.</div>;
    } else {
      body = (
        <>
          {profile.ambitionbox_rating != null && (
            <div className="tt-rating">
              &#9733; {profile.ambitionbox_rating.toFixed(1)}
              <span className="tt-rating-source">
                AmbitionBox{profile.ambitionbox_reviews_count ? ` · ${profile.ambitionbox_reviews_count.toLocaleString()} reviews` : ''}
              </span>
            </div>
          )}
          {facts.map(([label, value]) => (
            <div className="tt-row" key={label}><strong>{label}:</strong> {value}</div>
          ))}
          {(profile.tech_stack || []).length > 0 && (
            <div className="tt-row"><strong>Tech:</strong> {profile.tech_stack.join(', ')}</div>
          )}
          {profile.description && <p className="tt-desc">{profile.description}</p>}
        </>
      );
    }
  }

  return (
    <div className="company-tooltip" style={{ left: position.left, top: position.top }}>
      <div className="tt-name">{name}</div>
      {body}
    </div>
  );
}
