"""
FCC Ground Wave Curve Digitizer
Extracts (distance_km, field_strength_mVm) curves per conductivity from
FCC groundwave PDF graphs (vector-based, from fcc.gov/node/38972).
"""
import fitz
import numpy as np

CONDUCTIVITIES = ['5000','40','30','20','15','10','8','7','6','5','4','3','2','1.5','1','0.5','0.1']  # mS/m, high to low

def is_straight(items):
    pts=[]
    for it in items:
        if it[0]=='l': pts.append(it[1]); pts.append(it[2])
    if len(pts)<3: return True
    xs=[p.x for p in pts]; ys=[p.y for p in pts]
    if max(xs)-min(xs)<0.5 or max(ys)-min(ys)<0.5: return True
    return False

def get_clean_fragments(drawings):
    curves_raw = [d for d in drawings if len(d['items'])>5 and not is_straight(d['items'])]
    def get_pts(c):
        pts=[c['items'][0][1]]+[it[2] for it in c['items'] if it[0]=='l']
        return sorted(pts,key=lambda p:p.x)
    return [get_pts(c) for c in curves_raw]

def get_y_calibration(words):
    y_calib=[]
    for w in words:
        x0,y0,x1,y1,text = w[0],w[1],w[2],w[3],w[4]
        if x0<60 and 100<y0<1070:
            try:
                v=float(text); y_calib.append(((y0+y1)/2,v))
            except: pass
    y_calib = sorted(set(y_calib))
    ypx=np.array([c[0] for c in y_calib]); yval=np.array([np.log10(c[1]) for c in y_calib])
    def px_to_mvm(p): return 10**np.interp(p, ypx, yval)
    yval_rev = yval[::-1]; ypx_rev = ypx[::-1]
    def mvm_to_px(v): return np.interp(np.log10(v), yval_rev, ypx_rev)
    return px_to_mvm, mvm_to_px

def get_top_x_calibration(words):
    ticks={}
    for w in words:
        x0,y0,x1,y1,text = w[0],w[1],w[2],w[3],w[4]
        if 105<y0<117 and 60<x0<720 and text in ('.1','1','10','50'):
            ticks[text]=x0
    vals={'.1':0.1,'1':1,'10':10,'50':50}
    xpx=np.array([ticks[k] for k in ticks]); xval=np.array([np.log10(vals[k]) for k in ticks])
    def px_to_km(p): return 10**np.interp(p, xpx, xval)
    def km_to_px(km): return np.interp(np.log10(km), xval, xpx)
    return px_to_km, km_to_px

def get_bottom_x_calibration(words):
    ticks={}
    for w in words:
        x0,y0,x1,y1,text = w[0],w[1],w[2],w[3],w[4]
        if 1065<y0<1080:
            if text=='10' and ('10' not in ticks or x0<ticks['10']):
                ticks['10']=x0
            if text=='5000':
                ticks['5000']=x0
    xpx=np.array([ticks['10'],ticks['5000']]); xval=np.array([np.log10(10),np.log10(5000)])
    def px_to_km(p): return 10**np.interp(p, xpx, xval)
    def km_to_px(km): return np.interp(np.log10(km), xval, xpx)
    return px_to_km, km_to_px

def get_legend_anchors(drawings):
    pts=[]
    for d in drawings:
        for it in d['items']:
            if it[0]=='l':
                p1,p2=it[1],it[2]
                if 716<p2.x<722 and 708<p1.x<719: pts.append(round(p2.y,1))
                if 716<p1.x<722 and 708<p2.x<719: pts.append(round(p1.y,1))
    pts=sorted(set(pts))
    clean=[p for p in pts if any(abs(p-q)<3 and p!=q for q in pts)]
    if not clean or len(clean)%2!=0: return None
    clusters = [float((clean[i]+clean[i+1])/2) for i in range(0, len(clean), 2)]
    if len(clusters)!=17: return None
    return dict(zip(CONDUCTIVITIES, clusters))

def splice_inverse_distance(frag, px_to_km, km_to_px, px_to_mvm, mvm_to_px, x_left=72.0):
    if frag[0].x - x_left < 2:
        return frag
    xs = np.linspace(x_left, frag[0].x, 12)
    synth=[]
    for xp in xs:
        km = px_to_km(xp)
        mvm = 100.0/km
        yp = mvm_to_px(mvm)
        synth.append(fitz.Point(xp,yp))
    return synth[:-1] + frag

def curve_to_km_mvm(pts, px_to_km, px_to_mvm):
    return [(float(px_to_km(p.x)), float(px_to_mvm(p.y))) for p in pts]


def assign_all_curves(pdf_path):
    """Full pipeline: returns (top_result, bottom_result, notes) where notes lists any
    approximations made (e.g. a merged-curve duplicate at low frequency)."""
    doc = fitz.open(pdf_path)
    page = doc[0]
    words = page.get_text('words')
    drawings = page.get_drawings()
    notes = []

    fragments = get_clean_fragments(drawings)
    px_to_mvm, mvm_to_px = get_y_calibration(words)
    top_px_to_km, top_km_to_px = get_top_x_calibration(words)
    bot_px_to_km, bot_km_to_px = get_bottom_x_calibration(words)

    top_candidates = [(i,f) for i,f in enumerate(fragments) if f[-1].x >= 700]
    bottom_candidates = [(i,f) for i,f in enumerate(fragments) if f[-1].x < 700]

    if len(bottom_candidates) != 17:
        raise ValueError(f"Expected 17 bottom-panel fragments, got {len(bottom_candidates)}")

    # --- Assign top curves ---
    # Curves are physically non-crossing (higher conductivity = less attenuation =
    # higher field strength everywhere), so rank-ordering by right-edge y-position is
    # used as the primary method. The legend was tried first but proved fragile for
    # closely-spaced labels (greedy nearest-anchor matching occasionally swapped
    # adjacent pairs like 30/40 or 15/20 mS/m); it's now only used as a confidence
    # cross-check, not for assignment.
    legend = get_legend_anchors(drawings)
    top_assigned_px = None

    if len(top_candidates) == 17:
        ranked = sorted(top_candidates, key=lambda t: t[1][-1].y)
        top_assigned_px = {label: fragments[i] for (i,f), label in zip(ranked, CONDUCTIVITIES)}
    elif len(top_candidates) == 16:
        # One conductivity's curve merged with a neighbor in the source artwork
        # (common at low frequencies). Use bottom-panel continuity at km=10 to
        # find the best-fit missing label, then duplicate its nearest neighbor.
        ranked = sorted(top_candidates, key=lambda t: t[1][-1].y)
        x10 = top_km_to_px(10)
        top_vals=[]
        for i,f in ranked:
            xs=[p.x for p in f]; ys=[p.y for p in f]
            y10=np.interp(x10,xs,ys)
            top_vals.append(px_to_mvm(y10))
        top_log = np.log10(sorted(top_vals, reverse=True))
        bottom_vals = sorted([px_to_mvm(f[0].y) for i,f in bottom_candidates], reverse=True)
        bottom_log = np.log10(bottom_vals)
        best_skip=None; best_err=1e9
        for skip in range(17):
            remaining = np.delete(bottom_log, skip)
            err = np.sum((remaining-top_log)**2)
            if err<best_err: best_err=err; best_skip=skip
        missing_label = CONDUCTIVITIES[best_skip]
        remaining_labels = [l for l in CONDUCTIVITIES if l != missing_label]
        top_assigned_px = {label: fragments[i] for (i,f), label in zip(ranked, remaining_labels)}
        neighbor_idx = best_skip-1 if best_skip>0 else best_skip+1
        neighbor_label = CONDUCTIVITIES[neighbor_idx]
        top_assigned_px[missing_label] = top_assigned_px[neighbor_label]
        notes.append(f"{missing_label} mS/m curve visually merged with {neighbor_label} mS/m "
                     f"in source artwork (top panel, 0.1-50km); duplicated from nearest neighbor.")
    else:
        raise ValueError(f"Top panel: found {len(top_candidates)} candidate curves, expected 17 or 16")

    # --- Splice inverse-distance for any top curves not starting near x=72 ---
    top_result={}
    for label, frag in top_assigned_px.items():
        full = splice_inverse_distance(frag, top_px_to_km, top_km_to_px, px_to_mvm, mvm_to_px)
        top_result[label] = curve_to_km_mvm(full, top_px_to_km, px_to_mvm)

    # --- Assign bottom curves by rank order ---
    # Bottom-panel curves, like top-panel curves, are non-crossing (higher conductivity
    # = higher field strength = smaller y-pixel throughout). Rank-ordering by y-position
    # at the panel's left edge (km=10) is more robust than greedy nearest-value matching
    # against top-panel continuity, which is fragile when adjacent conductivities' values
    # are numerically close (this previously caused a 20/30 mS/m mislabeling).
    if len(bottom_candidates) != 17:
        raise ValueError(f"Expected 17 bottom-panel fragments, got {len(bottom_candidates)}")
    ranked_bottom = sorted(bottom_candidates, key=lambda t: t[1][0].y)
    bottom_assigned = {label: frag for (i,frag), label in zip(ranked_bottom, CONDUCTIVITIES)}

    bottom_result={}
    for label, frag in bottom_assigned.items():
        bottom_result[label] = curve_to_km_mvm(frag, bot_px_to_km, px_to_mvm)

    return top_result, bottom_result, notes
