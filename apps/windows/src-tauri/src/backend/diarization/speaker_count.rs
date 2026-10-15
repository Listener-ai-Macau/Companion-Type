//! Acoustic normalized maximum eigengap counting, followed by the caller's
//! existing constrained AHC. Inspired by Park et al., IEEE SPL 27 (2019),
//! https://arxiv.org/abs/2003.02405 and NVIDIA NeMo offline_clustering.py.
//! This is an independently implemented NME counting step, not NeMo's complete
//! spectral-label assignment. No transcript, names or expected count is read.
use nalgebra::{DMatrix, SymmetricEigen};

const MIN_OBSERVATIONS: usize = 12;
const MAX_MATRIX: usize = 256;
const MAX_ESTIMATE: usize = 8;

/// A short recording cannot supply the observations required by NME. Compare
/// cuts of the same constrained average-link tree using cosine silhouette,
/// rather than treating every below-threshold variation as a new person.
/// Only rejoin an existing >=3-group hypothesis; never create extra people,
/// erase the last two voices, override provider identities or affect long NME.
/// Silhouette follows Rousseeuw (1987), doi:10.1016/0377-0427(87)90125-7.
pub(super) fn refine_short_cut(vectors:&[Vec<f32>],
    constraints:&[Option<super::SpeakerConstraint>],baseline:&[usize])->Option<Vec<usize>> {
    let n=vectors.len();
    if !(3..MIN_OBSERVATIONS).contains(&n) || baseline.len()!=n { return None; }
    let width=vectors.first()?.len();
    if width==0 || vectors.iter().any(|v|v.len()!=width || v.iter().any(|x|!x.is_finite())
        || v.iter().map(|&x|f64::from(x).powi(2)).sum::<f64>()<1e-16) { return None; }
    let count=baseline.iter().copied().collect::<std::collections::BTreeSet<_>>().len();
    if count<3 { return None; }
    let mut distances=vec![vec![0.0;n];n];
    for i in 0..n {for j in 0..i {
        let distance=(1.0-f64::from(super::cosine(&vectors[i],&vectors[j]))).clamp(0.0,2.0);
        distances[i][j]=distance;distances[j][i]=distance;
    }}
    let mut best_score=silhouette(&distances,baseline)?;let mut best=None;
    for groups in 2..count {
        // The existing merge routine preserves same-request cannot-link and
        // must-link identities. A requested cut is not a forced people count.
        let labels=super::ahc_cluster_with_minimum(vectors,-1.0,constraints,groups);
        let Some(score)=silhouette(&distances,&labels) else {continue;};
        if score>best_score+1e-9 {best_score=score;best=Some(labels);}
    }
    best
}

fn silhouette(distances:&[Vec<f64>],labels:&[usize])->Option<f64> {
    let groups=labels.iter().copied().collect::<std::collections::BTreeSet<_>>();
    if labels.len()<2 || groups.len()<2 || distances.len()!=labels.len() {return None;}
    let mut sum=0.0;
    for (i,&label) in labels.iter().enumerate() {
        let own=labels.iter().enumerate().filter(|&(j,&group)|j!=i && group==label).map(|(j,_)|j).collect::<Vec<_>>();
        // Conventional silhouette of a singleton is zero, not perfect unity.
        if own.is_empty() {continue;}
        let a=own.iter().map(|&j|distances[i][j]).sum::<f64>()/own.len() as f64;
        let b=groups.iter().filter(|&&group|group!=label).map(|&group| {
            let members=labels.iter().enumerate().filter(|&(_,&g)|g==group).map(|(j,_)|j).collect::<Vec<_>>();
            members.iter().map(|&j|distances[i][j]).sum::<f64>()/members.len() as f64
        }).min_by(f64::total_cmp)?;
        let scale=a.max(b);if scale>1e-12 {sum+=(b-a)/scale;}
    }
    Some(sum/labels.len() as f64)
}

pub(super) fn estimate(vectors: &[Vec<f32>]) -> Option<usize> {
    let n = vectors.len();
    if n < MIN_OBSERVATIONS { return None; }
    // Do not silently subsample away a brief speaker in a long meeting. The
    // current bounded counting path declines above this size; AHC still runs
    // on every original vector, with its existing threshold/constraints.
    if n > MAX_MATRIX { return None; }
    let dim = vectors.first()?.len();
    if dim == 0 || vectors.iter().any(|v| v.len()!=dim || v.iter().any(|x| !x.is_finite())) { return None; }
    let norms = vectors.iter().map(|v| v.iter().map(|&x| f64::from(x).powi(2)).sum::<f64>().sqrt()).collect::<Vec<_>>();
    if norms.iter().any(|&v| v<1e-8) { return None; }
    let mut affinity=DMatrix::zeros(n,n);
    for i in 0..n {
        for j in 0..=i {
            let value=vectors[i].iter().zip(&vectors[j]).map(|(&a,&b)|f64::from(a)*f64::from(b)).sum::<f64>()/(norms[i]*norms[j]);
            affinity[(i,j)]=value;affinity[(j,i)]=value;
        }
        affinity[(i,i)]=1.0;
    }
    // A nearly constant affinity matrix has arbitrary nearest-neighbour
    // rank ties, not evidence of several people.
    if affinity.iter().all(|&value|value>=0.9) { return Some(1); }
    let mut order=Vec::with_capacity(n);
    for i in 0..n {
        let mut row=(0..n).collect::<Vec<_>>();
        row.sort_by(|&a,&b|affinity[(i,b)].total_cmp(&affinity[(i,a)]).then(a.cmp(&b)));
        order.push(row);
    }
    let mut trials:Vec<(f64,usize,bool)>=Vec::new();
    // Include self among the p nearest entries, as in the reference method.
    // The self-edge cancels in D-A. Search is capped by 25% graph density.
    for p in 2..=(n/4).max(2) {
        let mut graph=DMatrix::zeros(n,n);
        for i in 0..n { for &j in order[i].iter().take(p) { graph[(i,j)]=1.0; } }
        let mut lap=DMatrix::zeros(n,n);
        for i in 0..n {
            for j in 0..n {
                if i==j { continue; }
                let weight=(graph[(i,j)]+graph[(j,i)])*0.5;
                lap[(i,j)]=-weight;lap[(i,i)]+=weight;
            }
        }
        let mut seen=vec![false;n];let mut pending=vec![0];seen[0]=true;
        while let Some(i)=pending.pop() {
            for j in 0..n { if !seen[j] && lap[(i,j)]<0.0 { seen[j]=true;pending.push(j); } }
        }
        let connected=seen.into_iter().all(|x|x);
        let mut eigen=SymmetricEigen::try_new(lap,1e-10,100_000)?.eigenvalues.as_slice().to_vec();
        eigen.sort_by(f64::total_cmp);
        if eigen.iter().any(|x|!x.is_finite()) { return None; }
        let mut chosen=(0.0,1usize);
        for k in 1..=MAX_ESTIMATE.min(n-1) {
            let gap=(eigen[k]-eigen[k-1]).max(0.0);
            if gap>chosen.0 { chosen=(gap,k); }
        }
        if chosen.0<=1e-8 { continue; }
        let normalized_gap=chosen.0/(eigen[n-1].max(0.0)+1e-10);
        let ratio=(p as f64/n as f64)/(normalized_gap+1e-10);
        trials.push((ratio,chosen.1,connected));
    }
    let best=trials.iter().min_by(|a,b|a.0.total_cmp(&b.0))?;
    // As in the reference NME procedure, an overly sparse disconnected graph
    // must not turn local rank variation into extra people. Raise density to
    // the first connected graph, or the largest searched graph if needed.
    let selected=if best.2 {best}else{trials.iter().find(|t|t.2).or_else(||trials.last())?};
    Some(selected.1)
}

#[cfg(test)] mod tests {
    use super::*;
    #[test] fn short_tree_can_rejoin_voice_variation_without_merging_distinct_provider_identities() {
        let vectors=vec![vec![1.0,0.0],vec![-1.0,0.0],vec![0.8,0.6],vec![0.8,-0.6]];
        let labels=super::super::cluster_speakers(&vectors);
        assert_eq!(labels[0],labels[2]);assert_eq!(labels[0],labels[3]);assert_ne!(labels[0],labels[1]);
        let constraints=vec![Some(super::super::SpeakerConstraint{request:0,label:"A".into()}),
            None,None,Some(super::super::SpeakerConstraint{request:0,label:"B".into()})];
        let constrained=super::super::cluster_speakers_constrained(&vectors,&constraints);
        assert_ne!(constrained[0],constrained[3]);
    }
    #[test] fn short_cut_keeps_singletons_neutral_and_declines_long_or_invalid_input() {
        assert_eq!(silhouette(&[vec![0.0,1.0],vec![1.0,0.0]],&[0,1]),Some(0.0));
        assert!(refine_short_cut(&vec![vec![1.0,0.0];12],&[],&vec![0;12]).is_none());
        assert!(refine_short_cut(&vec![vec![f32::NAN,0.0];4],&[],&[0,1,2,3]).is_none());
        assert!(refine_short_cut(&vec![vec![1.0,0.0];4],&[],&[0,0,1,1]).is_none());
    }
    fn groups(count:usize)->Vec<Vec<f32>> {
        (0..count).flat_map(|group|(0..16).map(move |i| {
            let mut v=vec![0.15;count+2];v[group]=1.0;v[count]=0.001*i as f32;v
        })).collect()
    }
    #[test] fn full_refiner_does_not_split_one_or_two_voices_on_graph_rank_ties() {
        for n in 1..=4 {
            let mut observations=groups(n);
            for vector in &mut observations { super::super::normalize(vector); }
            let labels=super::super::cluster_speakers(&observations);
            assert_eq!(labels.into_iter().collect::<std::collections::BTreeSet<_>>().len(),n);
        }
    }
    #[test] fn refuses_unqualified_input_instead_of_guessing() {
        assert_eq!(estimate(&groups(1)[..4]),None);
        assert_eq!(estimate(&vec![vec![f32::NAN;3];16]),None);
        assert_eq!(estimate(&vec![vec![0.0;3];16]),None);
        assert_eq!(estimate(&vec![vec![1.0;3];MAX_MATRIX+1]),None);
    }
}
