ROLES=('admin','analyst','viewer')
STATES=('queued','running','done','failed')
FEATURES=('pressure','flow','temperature','machines','sensor_noise')
REVIEW_STATES=('draft','approved')
# 仪表纠偏：仅工况与耗电字段可在分支内修订，小时键与计量说明不在试算合并范围
CORRECTION_FIELDS=('pressure','flow','temperature','machines','sensor_noise','kwh')
BRANCH_STATES=('draft','trialing','trial_failed','ready','publishing','publish_failed','published','conflict')
TRIAL_STATES=('queued','running','done','failed')
RUN_QUEUE='airpower:runs'
TRIAL_QUEUE='airpower:trials'
PUBLISH_QUEUE='airpower:publishes'
