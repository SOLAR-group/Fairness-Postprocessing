import os
os.environ["OMP_NUM_THREADS"] = "1" # export OMP_NUM_THREADS=1
os.environ["OPENBLAS_NUM_THREADS"] = "1" # export OPENBLAS_NUM_THREADS=1
os.environ["MKL_NUM_THREADS"] = "1" # export MKL_NUM_THREADS=1
os.environ["VECLIB_MAXIMUM_THREADS"] = "1" # export VECLIB_MAXIMUM_THREADS=1
os.environ["NUMEXPR_NUM_THREADS"] = "1" # export NUMEXPR_NUM_THREADS=1
import sys
sys.path.append("../")
import warnings
warnings.filterwarnings('ignore')
import numpy as np

from sklearn import metrics

import argparse
import random
from aif360.metrics import BinaryLabelDatasetMetric
from aif360.metrics import ClassificationMetric
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

from aif360.datasets import AdultDataset, GermanDataset, CompasDataset
from utility import get_data,write_to_file
from sklearn.base import clone
import copy



parser = argparse.ArgumentParser()
parser.add_argument("-d", "--dataset", type=str, default="adult",
                    help="Dataset name")
parser.add_argument("-p", "--protected", type=str, default="sex",
                    help="Protected attribute")

parser.add_argument("-s", "--start", type=int, default=0,
                    help="Start")
parser.add_argument("-e", "--end", type=int, default=30,
                    help="End")
parser.add_argument("-t", "--trials", type=int, default=50,
                    help="Trials")
parser.add_argument("-o", "--operations", type=int, default=5000,
                    help="Operations")
parser.add_argument("-m", "--metric", type=int, default=0,
                    help="metric")
# parser.add_argument("-n", "--noise", type=float, default=0.1,
#                     help="metric")
args = parser.parse_args()



dataset_used = args.dataset # "adult", "german", "compas"
attr = args.protected
start = args.start
end = args.end
trials = args.trials
operations = args.operations
metric_id = args.metric
#noise = args.noise



dataset_orig, privileged_groups,unprivileged_groups,optim_options = get_data(dataset_used, attr)

def get_metrics(clf,test,test_pred,unprivileged_groups,privileged_groups,reportAUC=False):
    pred = clf.predict(test.features).reshape(-1,1)
    #dataset_orig_test_pred = test.copy(deepcopy=True)
    test_pred.labels = pred
    class_metric = ClassificationMetric(test, test_pred,
                         unprivileged_groups=unprivileged_groups, privileged_groups=privileged_groups)
    stat = abs(class_metric.statistical_parity_difference())
    aod = abs(class_metric.average_abs_odds_difference())
    eod = abs(class_metric.equal_opportunity_difference())
    acc = class_metric.accuracy()
    precision = class_metric.precision()
    recall = class_metric.recall()
    auc = 0
    if reportAUC:
        fpr, tpr, thresholds = metrics.roc_curve(test.labels, test_pred.labels, pos_label=1)
        auc = metrics.auc(fpr, tpr)
    return acc,stat,aod,eod,precision,recall,auc

reporting_steps = [1000,2500]

# trials = 1
# end = 1
for noise in [0.1]:
    val_name = "LR_{}_{}_{}_{}_{}_{}_{}_{}.txt".format(dataset_used,attr,start,end,trials,operations,metric_id,noise)
    val_name= os.path.join("results_lr",val_name)
    for t in range(start,trials):
        content = "Trial {}".format(t)
        write_to_file(val_name,content)
        np.random.seed(t)
        
        dataset_orig_train, dataset_orig_test = dataset_orig.split([0.7], shuffle=True)
        dataset_orig_test,dataset_orig_valid = dataset_orig_test.split([0.5], shuffle=True)
        dataset_orig_test_pred = dataset_orig_test.copy(deepcopy=True)
        dataset_orig_train_pred = dataset_orig_train.copy(deepcopy=True)
        dataset_orig_valid_pred = dataset_orig_valid.copy(deepcopy=True)    

        for r in range(0,end):
            clf = LogisticRegression()
            clf = clf.fit(dataset_orig_train.features, dataset_orig_train.labels)
            _,n = clf.coef_.shape
            #try:
            #train_acc,train_stat,train_aod,train_eod = get_metrics(clf,dataset_orig_train,dataset_orig_train_pred,unprivileged_groups,privileged_groups)
            #test_acc,test_stat,test_aod,test_eod = get_metrics(clf,dataset_orig_test,dataset_orig_test_pred,unprivileged_groups,privileged_groups)
            valid_acc,valid_stat,valid_aod,valid_eod,valid_prec,valid_recall,valid_auc = get_metrics(clf,dataset_orig_valid,dataset_orig_valid_pred,unprivileged_groups,privileged_groups)
            valid_fair = [valid_stat,valid_aod,valid_eod][metric_id]
            hist = [(valid_acc,valid_fair)]
            hist_steps = []
            for op in range(operations):
                if op in reporting_steps:
                    content = "Run {} - Steps {}".format(r,op)
                    
                    write_to_file(val_name,content)
                    write_to_file(val_name," ".join(map(str,hist_steps)))
                    hist_steps = []
                    test_acc,test_stat,test_aod,test_eod,test_prec,test_recall,test_auc = get_metrics(clf,dataset_orig_test,dataset_orig_test_pred,unprivileged_groups,privileged_groups,reportAUC=True)
                    content = "{} {} {} {} {} {} {}".format(test_acc,test_stat,test_aod,test_eod,test_prec,test_recall,test_auc)
                    write_to_file(val_name,content)

                    valid_acc,valid_stat,valid_aod,valid_eod,valid_prec,valid_recall,valid_auc = get_metrics(clf,dataset_orig_valid,dataset_orig_valid_pred,unprivileged_groups,privileged_groups,reportAUC=True)
                    content = "{} {} {} {} {} {} {}".format(valid_acc,valid_stat,valid_aod,valid_eod,valid_prec,valid_recall,valid_auc)
                    write_to_file(val_name,content)
                i = random.randint(0,n)
                change = 1+np.random.uniform(-noise,noise,1)[0]
                if i == n:
                    clf.intercept_*=change
                else:
                    clf.coef_[0][i] *=change
                valid_acc,valid_stat,valid_aod,valid_eod,valid_prec,valid_recall,valid_auc = get_metrics(clf,dataset_orig_valid,dataset_orig_valid_pred,unprivileged_groups,privileged_groups)  
                valid_fair = [valid_stat,valid_aod,valid_eod][metric_id]    
                prev_valid_acc,prev_valid_fair = hist[-1]
                if valid_fair < prev_valid_fair and valid_acc>prev_valid_acc:
                    hist.append((valid_acc,valid_fair))
                    hist_steps.append(op)
                else:
                    rev_change = 1/change
                    if n == i:
                        clf.intercept_*=rev_change
                    else:
                        clf.coef_[0][i] *=rev_change

            
            #train_acc,train_stat,train_aod,train_eod = get_metrics(clf,dataset_orig_train,dataset_orig_train_pred,unprivileged_groups,privileged_groups)
            test_acc,test_stat,test_aod,test_eod,test_prec,test_recall,test_auc = get_metrics(clf,dataset_orig_test,dataset_orig_test_pred,unprivileged_groups,privileged_groups,reportAUC=True)
            #valid_acc,valid_stat,valid_aod,valid_eod = get_metrics(clf,dataset_orig_valid,dataset_orig_valid_pred,unprivileged_groups,privileged_groups)
            content = "Run {} - Steps {}".format(r,operations)
            write_to_file(val_name,content)
            write_to_file(val_name," ".join(map(str,hist_steps)))
            #content = "{} {} {} {}".format(train_acc,train_stat,train_aod,train_eod)
            #write_to_file(val_name,content)
            content = "{} {} {} {} {} {} {}".format(test_acc,test_stat,test_aod,test_eod,test_prec,test_recall,test_auc)
            write_to_file(val_name,content)
            valid_acc,valid_stat,valid_aod,valid_eod,valid_prec,valid_recall,valid_auc = get_metrics(clf,dataset_orig_valid,dataset_orig_valid_pred,unprivileged_groups,privileged_groups,reportAUC=True)
            content = "{} {} {} {} {} {} {}".format(valid_acc,valid_stat,valid_aod,valid_eod,valid_prec,valid_recall,valid_auc)
            write_to_file(val_name,content)
            #content = "{} {} {} {}".format(valid_acc,valid_stat,valid_aod,valid_eod)
            #write_to_file(val_name,content)
            # except:
            #     end+=1
write_to_file(val_name,"done")