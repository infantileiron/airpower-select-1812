/** @typedef {{id:number,hour:string,pressure:number,flow:number,temperature:number,machines:number,sensor_noise:number,kwh:number,note:string}} Sample */
/** @typedef {{id:number,name:string,features:string[],alphas:number[],state:string,result:object,error:string,source_branch_id?:number}} Run */
/** @typedef {{id:number,run_id:number,title:string,finding:string,action:string,status:string}} Review */
/** @typedef {{id:number,name:string,status:string,baseline:object[],baseline_checksum:string,current_checksum:string,features:string[],alphas:number[],trial_id:number,trial_result:object,error:string,published_run_id:number,change_count:number,diff:object[]}} CorrectionBranch */
/** @typedef {{id:number,branch_id:number,features:string[],alphas:number[],state:string,result:object,error:string}} Trial */
