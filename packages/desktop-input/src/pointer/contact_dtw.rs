//! GRT DTW port, MIT, pinned 4d4cab1999a349b00d8924da769ff3f0c29d3176.
//! Original and license: third_party/imu-pointer/grt/DTW.cpp. This deliberately
//! preserves GRT's cumulative-path average (not ordinary DTW cost/path length),
//! constrained radius, recursion and tie order. Platform subset: 6 channels,
//! Euclidean distance, constrained Z normalization, at most 32 rows. Host only.
pub type Series=Vec<[f64;6]>;
pub const MAX_ROWS:usize=32;

pub fn normalize(mut data:Series)->Series {
    for channel in 0..6 {
        let mean=data.iter().map(|x|x[channel]).sum::<f64>()/data.len()as f64;
        let deviation=(data.iter().map(|x|(x[channel]-mean).powi(2)).sum::<f64>()/(data.len()-1)as f64).sqrt();
        for row in &mut data{row[channel]=(row[channel]-mean)/if deviation<0.01{1.}else{deviation};}
    }
    data
}

pub fn distance(a:&[[f64;6]],b:&[[f64;6]])->f64 {
    let m=a.len();let n=b.len();
    if !(2..=MAX_ROWS).contains(&m)||!(2..=MAX_ROWS).contains(&n){return f64::INFINITY;}
    let mut cost=vec![vec![0.;n];m];
    for i in 0..m{for j in 0..n{cost[i][j]=a[i].iter().zip(b[j]).map(|(x,y)|(x-y).powi(2)).sum::<f64>().sqrt();}}
    if !visit(m-1,n-1,&mut cost,m,n).sqrt().is_finite(){return f64::INFINITY;}
    for row in &mut cost{for x in row{*x=x.abs();}}
    let(mut i,mut j)=(m-1,n-1);let mut total=cost[i][j];let mut count=1;
    while i!=0||j!=0 {
        if i==0{j-=1;}else if j==0{i-=1;}else{
            let mut v=f64::MAX;let mut index=0;
            if cost[i-1][j]<v{v=cost[i-1][j];index=1;}
            if cost[i][j-1]<v{v=cost[i][j-1];index=2;}
            if cost[i-1][j-1]<=v{index=3;}
            match index{1=>i-=1,2=>j-=1,3=>{i-=1;j-=1;},_=>return f64::INFINITY}
        }
        total+=cost[i][j];count+=1;
    }
    total/count as f64
}
fn visit(i:usize,j:usize,c:&mut [Vec<f64>],m:usize,n:usize)->f64 {
    if c[i][j].is_nan(){return f64::NAN;}
    let radius=(m.min(n)as f64*0.2).ceil();
    // Keep the upstream floating point formula, including its i==0 infinity.
    let offset=j as f64-((n-1)as f64/((m-1)as f64/i as f64));
    if offset.abs()>radius {
        if offset>0.{for row in c.iter_mut().take(i){for x in row.iter_mut().skip(j){*x=f64::NAN;}}}
        else{for row in c.iter_mut().skip(i){for x in row.iter_mut().take(j){*x=f64::NAN;}}}
        return f64::NAN;
    }
    if c[i][j].is_sign_negative(){return c[i][j].abs();}
    let value=if i==0&&j==0{c[0][0]}
        else if i==0{c[i][j]+visit(i,j-1,c,m,n)}
        else if j==0{c[i][j]+visit(i-1,j,c,m,n)}
        else{
            let options=[visit(i-1,j-1,c,m,n),visit(i-1,j,c,m,n),visit(i,j-1,c,m,n)];
            let mut min=f64::MAX;let mut found=false;
            for v in options{if v<min{min=v;found=true;}}
            if found{c[i][j]+min}else{0.}
        };
    c[i][j]=-value;value
}

/// GRT train_NDDTW medoid and mean + 3*sigma template rejection threshold.
pub fn train(samples:&[Series])->Option<(Series,f64)> {
    if samples.len()<3{return None;}
    let d:Vec<Vec<f64>>=samples.iter().map(|a|samples.iter().map(|b|distance(a,b)).collect()).collect();
    let means:Vec<f64>=d.iter().enumerate().map(|(i,row)|row.iter().enumerate().filter(|(j,_)|*j!=i).map(|(_,x)|x).sum::<f64>()/(samples.len()-1)as f64).collect();
    let index=(0..samples.len()).min_by(|&i,&j|means[i].total_cmp(&means[j]))?;
    let mu=means[index];
    let sigma=(d[index].iter().enumerate().filter(|(i,_)|*i!=index).map(|(_,x)|(x-mu).powi(2)).sum::<f64>()/(samples.len()-2)as f64).sqrt();
    Some((samples[index].clone(),mu+3.*sigma))
}
