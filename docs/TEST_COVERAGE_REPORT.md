# گزارش جامع تست‌ها و نرخ هم‌پوشانی (Coverage) BHAM

**محصول:** BHAM — Barrier Health & Alarm Manager (نسخه ۲.۱.۰)
**تاریخ ارزیابی:** ۱۴۰۵/۰۸/۱۷
**ابزار:** pytest 9.0.2 + pytest-cov 7.0.0
**پلتفرم:** Python 3.12.16 / Linux

---

## ۱. خلاصه اجرایی

| شاخص | مقدار |
|---|---|
| **تعداد کل تست‌ها** | **۱۱۴ تست** |
| **تعداد فایل‌های تست** | ۹ فایل |
| **تست‌های موفق (PASSED)** | **۱۱۴ (۱۰۰٪)** ✅ |
| **تست‌های ناموفق (FAILED)** | ۰ |
| **تست‌های دارای خطا (ERROR)** | ۰ |
| **زمان اجرای کل** | ۱۰.۴۲ ثانیه |
| **نرخ هم‌پوشانی کلی (Coverage)** | **۹۳٪** |
| **تعداد خطوط کد (Stmts)** | ۱٬۴۴۶ |
| **خطوط پوشش‌داده‌نشده (Miss)** | ۱۰۷ (۷٪) |

### نتیجه کلی: ✅ همه ۱۱۴ تست موفق — نرخ هم‌پوشانی ۹۳٪

---

## ۲. نرخ هم‌پوشانی (Coverage) به تفکیک ماژول

| # | ماژول | خطوط (Stmts) | پوشش‌نداده (Miss) | **نرخ هم‌پوشانی** | وضعیت |
|---|---|---|---|---|---|
| ۱ | `config.py` | ۲۱ | ۰ | **۱۰۰٪** | ✅ کامل |
| ۲ | `tep_fault_detection.py` | ۷۲ | ۱ | **۹۹٪** | ✅ عالی |
| ۳ | `sequence_prediction.py` | ۱۲۶ | ۳ | **۹۸٪** | ✅ عالی |
| ۴ | `alarm_analytics.py` | ۳۷۳ | ۲۲ | **۹۴٪** | ✅ عالی |
| ۵ | `barrier_health.py` | ۱۹۹ | ۱۳ | **۹۳٪** | ✅ عالی |
| ۶ | `quality_optimizer.py` | ۳۰۵ | ۲۵ | **۹۲٪** | ✅ عالی |
| ۷ | `production_optimizer.py` | ۲۰۶ | ۲۲ | **۸۹٪** | ✅ خوب |
| ۸ | `dynamic_risk.py` | ۱۴۴ | ۲۱ | **۸۵٪** | ✅ خوب |
| **کل** | **۹ فایل** | **۱٬۴۴۶** | **۱۰۷** | **۹۳٪** | ✅ |

### تحلیل نرخ هم‌پوشانی
- **۴ ماژول با coverage ≥ ۹۴٪** (عالی): config، tep، sequence، alarm
- **۳ ماژول با coverage ۸۹-۹۳٪** (خوب): barrier، quality، production
- **۱ ماژول با coverage ۸۵٪** (قابل قبول): dynamic_risk
- میانگین وزنی coverage: **۹۳٪** (فراتر از آستانه صنعتی ۸۰٪)

---

## ۳. فهرست کامل ۱۱۴ تست انجام‌شده

### ۳.۱ فایل `test_alarm_analytics.py` — ۶ تست (همه موفق ✅)

| # | نام تست | توصیف | وضعیت |
|---|---|---|---|
| ۱ | `test_metrics_basic` | محاسبه شاخص‌های پایه آلارم | ✅ PASSED |
| ۲ | `test_metrics_full_v2` | شاخص‌های کامل نسخه ۲ (EEMUA) | ✅ PASSED |
| ۳ | `test_chattering_detection` | تشخیص آلارم‌های چاترینگ | ✅ PASSED |
| ۴ | `test_stale_alarms` | تشخیص آلارم‌های کهنه (stale) | ✅ PASSED |
| ۵ | `test_flood_detection` | تشخیص سیلاب آلارم | ✅ PASSED |
| ۶ | `test_anomaly_detection` | تشخیص ناهنجاری با Isolation Forest | ✅ PASSED |

### ۳.۲ فایل `test_api.py` — ۸ تست (همه موفق ✅)

| # | نام تست | توصیف | وضعیت |
|---|---|---|---|
| ۱ | `test_dashboard_root` | ریشه داشبورد API | ✅ PASSED |
| ۲ | `test_health_endpoint` | endpoint سلامت سیستم | ✅ PASSED |
| ۳ | `test_analyze_alarms_endpoint` | endpoint تحلیل آلارم | ✅ PASSED |
| ۴ | `test_barrier_health_endpoint` | endpoint سلامت لایه‌ها | ✅ PASSED |
| ۵ | `test_sequence_predict_endpoint` | endpoint پیش‌بینی توالی | ✅ PASSED |
| ۶ | `test_risk_estimate_endpoint` | endpoint تخمین ریسک | ✅ PASSED |
| ۷ | `test_metrics_summary_endpoint` | endpoint خلاصه شاخص‌ها | ✅ PASSED |
| ۸ | `test_error_handling_invalid_payload` | مدیریت خطای payload نامعتبر | ✅ PASSED |

### ۳.۳ فایل `test_barrier_health.py` — ۷ تست (همه موفق ✅)

| # | نام تست | توصیف | وضعیت |
|---|---|---|---|
| ۱ | `test_compute_layer_health_returns_layer_objects` | محاسبه سلامت لایه‌ها | ✅ PASSED |
| ۲ | `test_aggregate_unit_risk_in_range` | تجمیع ریسک واحد در بازه | ✅ PASSED |
| ۳ | `test_simultaneous_weakness` | تشخیص ضعف همزمان لایه‌ها | ✅ PASSED |
| ۴ | `test_sil_computation` | محاسبه سطح یکپارچگی ایمنی (SIL) | ✅ PASSED |
| ۵ | `test_sil_gap_detection` | تشخیص شکاف SIL | ✅ PASSED |
| ۶ | `test_test_interval_based_on_sil` | فاصله تست مبتنی بر SIL | ✅ PASSED |
| ۷ | `test_optimize_test_intervals_returns_df` | بهینه‌سازی فواصل تست | ✅ PASSED |

### ۳.۴ فایل `test_benchmark_features.py` — ۲۹ تست (همه موفق ✅)

این فایل شامل تست‌های جامع ویژگی‌ها و پیکربندی سیستم است:

| # | نام تست | توصیف | وضعیت |
|---|---|---|---|
| ۱ | `test_package_version` | نسخه بسته | ✅ PASSED |
| ۲ | `test_data_directories_exist` | وجود دایرکتوری‌های داده | ✅ PASSED |
| ۳ | `test_module_configs_present` | حضور پیکربندی ماژول‌ها | ✅ PASSED |
| ۴ | `test_eemua_targets_constant` | ثابت‌های هدف EEMUA | ✅ PASSED |
| ۵ | `test_sil_targets_constant` | ثابت‌های هدف SIL | ✅ PASSED |
| ۶ | `test_oee_targets_constant` | ثابت‌های هدف OEE | ✅ PASSED |
| ۷ | `test_western_electric_rules_constant` | قوانین Western Electric | ✅ PASSED |
| ۸ | `test_protection_layers_complete` | تکمیل لایه‌های حفاظتی | ✅ PASSED |
| ۹ | `test_priority_distribution` | توزیع اولویت آلارم | ✅ PASSED |
| ۱۰ | `test_compliance_score_bounds` | کران امتیاز انطباق | ✅ PASSED |
| ۱۱ | `test_compliance_score_high_for_good_data` | امتیاز بالا برای داده خوب | ✅ PASSED |
| ۱۲ | `test_compliance_gaps_structure` | ساختار شکاف‌های انطباق | ✅ PASSED |
| ۱۳ | `test_compliance_report` | گزارش انطباق | ✅ PASSED |
| ۱۴ | `test_risk_level_thresholds` | آستانه‌های سطح ریسک | ✅ PASSED |
| ۱۵ | `test_risk_label_thresholds` | آستانه‌های برچسب ریسک | ✅ PASSED |
| ۱۶ | `test_threshold_recommendations` | پیشنهادات آستانه | ✅ PASSED |
| ۱۷ | `test_filter_shelved` | فیلتر آلارم‌های shelved | ✅ PASSED |
| ۱۸ | `test_filter_shelved_empty` | فیلتر shelved خالی | ✅ PASSED |
| ۱۹ | `test_shelve_single` | shelving تکی | ✅ PASSED |
| ۲۰ | `test_unshelve` | unshelving | ✅ PASSED |
| ۲۱ | `test_state_based_suppression` | سرکوب مبتنی بر حالت | ✅ PASSED |
| ۲۲ | `test_state_based_suppression_maintenance` | سرکوب حالت نگهداری | ✅ PASSED |
| ۲۳ | `test_cluster_groups_chattering` | خوشه‌بندی چاترینگ | ✅ PASSED |
| ۲۴ | `test_cluster_rationale` | منطق خوشه‌بندی | ✅ PASSED |
| ۲۵ | `test_rationalize_returns_records` | rationalize رکورد برمی‌گرداند | ✅ PASSED |
| ۲۶ | `test_rationalize_reorders_by_count` | rationalize مرتب بر اساس تعداد | ✅ PASSED |
| ۲۷ | `test_rationalize_with_custom_target` | rationalize با هدف سفارشی | ✅ PASSED |
| ۲۸ | `test_recommendation_text` | متن پیشنهاد | ✅ PASSED |
| ۲۹ | `test_dangerous_pattern_detected` | تشخیص الگوی خطرناک | ✅ PASSED |

### ۳.۵ فایل `test_dynamic_risk.py` — ۸ تست (همه موفق ✅)

| # | نام تست | توصیف | وضعیت |
|---|---|---|---|
| ۱ | `test_fit_returns_metrics` | fit شاخص‌ها برمی‌گرداند | ✅ PASSED |
| ۲ | `test_predict_returns_estimates` | predict تخمین برمی‌گرداند | ✅ PASSED |
| ۳ | `test_predict_before_fit_raises` | خطا قبل از fit | ✅ PASSED |
| ۴ | `test_feature_importances` | اهمیت ویژگی‌ها | ✅ PASSED |
| ۵ | `test_optimize_test_schedule` | بهینه‌سازی برنامه تست | ✅ PASSED |
| ۶ | `test_risk_label_thresholds` | آستانه‌های برچسب ریسک | ✅ PASSED |
| ۷ | `test_high_risk_score_increases_with_stress` | افزایش ریسک با فشار | ✅ PASSED |
| ۸ | `test_not_fitted_raises` | خطای not fitted | ✅ PASSED |

### ۳.۶ فایل `test_integration.py` — ۷ تست (همه موفق ✅)

| # | نام تست | توصیف | وضعیت |
|---|---|---|---|
| ۱ | `test_pipeline_end_to_end_synthetic` | پایپ‌لاین کامل داده مصنوعی | ✅ PASSED |
| ۲ | `test_pipeline_end_to_end_real` | پایپ‌لاین کامل داده واقعی | ✅ PASSED |
| ۳ | `test_real_tep_pipeline_runs` | اجرای پایپ‌لاین واقعی TEP | ✅ PASSED |
| ۴ | `test_all_modules_picklable` | قابلیت pickle همه ماژول‌ها | ✅ PASSED |
| ۵ | `test_empty_metrics` | شاخص‌های خالی | ✅ PASSED |
| ۶ | `test_empty_dataframe_metrics` | شاخص dataframe خالی | ✅ PASSED |
| ۷ | `test_predict_before_fit_raises` | خطا قبل از fit | ✅ PASSED |

### ۳.۷ فایل `test_quality_production.py` — ۳۶ تست (همه موفق ✅)

این بزرگ‌ترین فایل تست است و ماژول‌های کیفیت و تولید را پوشش می‌دهد:

| # | نام تست | توصیف | وضعیت |
|---|---|---|---|
| ۱ | `test_spc_basic` | کنترل آماری پایه | ✅ PASSED |
| ۲ | `test_spc_out_of_control_data` | SPC داده خارج از کنترل | ✅ PASSED |
| ۳ | `test_spc_empty_series` | SPC سری خالی | ✅ PASSED |
| ۴ | `test_spc_cusum_and_ewma` | CUSUM و EWMA | ✅ PASSED |
| ۵ | `test_spc_capability_grades` | گرید‌های قابلیت | ✅ PASSED |
| ۶ | `test_analyze_quality_variables` | تحلیل متغیرهای کیفی | ✅ PASSED |
| ۷ | `test_analyze_quality_variables_missing_column` | تحلیل با ستون مفقود | ✅ PASSED |
| ۸ | `test_fault_quality_impact` | اثر کیفیت خطا | ✅ PASSED |
| ۹ | `test_fault_quality_impact_missing_col` | اثر خطا با ستون مفقود | ✅ PASSED |
| ۱۰ | `test_fault_quality_impact_sorted` | اثر خطا مرتب | ✅ PASSED |
| ۱۱ | `test_fault_quality_impact_with_descriptions` | اثر خطا با توضیحات | ✅ PASSED |
| ۱۲ | `test_quality_report` | گزارش کیفیت | ✅ PASSED |
| ۱۳ | `test_quality_report_with_faults` | گزارش کیفیت با خطاها | ✅ PASSED |
| ۱۴ | `test_root_cause_analysis` | تحلیل علت ریشه‌ای | ✅ PASSED |
| ۱۵ | `test_root_cause_no_violations` | علت ریشه‌ای بدون نقض | ✅ PASSED |
| ۱۶ | `test_optimize_setpoint_with_correlation` | بهینه‌سازی setpoint با همبستگی | ✅ PASSED |
| ۱۷ | `test_optimize_setpoint_no_correlation` | بهینه‌سازی setpoint بدون همبستگی | ✅ PASSED |
| ۱۸ | `test_optimize_setpoint_empty_df` | بهینه‌سازی setpoint dataframe خالی | ✅ PASSED |
| ۱۹ | `test_compute_kpis` | محاسبه KPI تولید | ✅ PASSED |
| ۲۰ | `test_compute_kpis_empty_df` | KPI با dataframe خالی | ✅ PASSED |
| ۲۱ | `test_oee_computation` | محاسبه OEE | ✅ PASSED |
| ۲۲ | `test_oee_world_class` | OEE کلاس جهانی | ✅ PASSED |
| ۲۳ | `test_oee_critical` | OEE بحرانی | ✅ PASSED |
| ۲۴ | `test_oee_reject_count` | تعداد رد OEE | ✅ PASSED |
| ۲۵ | `test_identify_bottlenecks` | شناسایی گلوگاه | ✅ PASSED |
| ۲۶ | `test_identify_bottlenecks_empty` | گلوگاه با ورودی خالی | ✅ PASSED |
| ۲۷ | `test_bottleneck_constraint_types` | انواع محدودیت گلوگاه | ✅ PASSED |
| ۲۸ | `test_analyze_yield` | تحلیل بازده | ✅ PASSED |
| ۲۹ | `test_analyze_yield_zero_feed` | بازده با feed صفر | ✅ PASSED |
| ۳۰ | `test_suggest_optimizations_strong_oee` | پیشنهاد بهبود OEE قوی | ✅ PASSED |
| ۳۱ | `test_suggest_optimizations_weak_oee` | پیشنهاد بهبود OEE ضعیف | ✅ PASSED |
| ۳۲ | `test_suggest_optimizations_sorted_by_roi` | پیشنهاد مرتب بر اساس ROI | ✅ PASSED |
| ۳۳ | `test_production_report` | گزارش تولید | ✅ PASSED |
| ۳۴ | `test_production_report_minimal` | گزارش تولید حداقلی | ✅ PASSED |
| ۳۵ | `test_bad_actor_identification` | شناسایی bad actor | ✅ PASSED |
| ۳۶ | `test_lopa_compliant` | انطباق LOPA | ✅ PASSED |

### ۳.۸ فایل `test_sequence_prediction.py` — ۶ تست (همه موفق ✅)

| # | نام تست | توصیف | وضعیت |
|---|---|---|---|
| ۱ | `test_fit_returns_metrics` | fit شاخص برمی‌گرداند | ✅ PASSED |
| ۲ | `test_predict_returns_predictions` | predict پیش‌بینی برمی‌گرداند | ✅ PASSED |
| ۳ | `test_predict_before_fit_raises` | خطا قبل از fit | ✅ PASSED |
| ۴ | `test_feature_importances` | اهمیت ویژگی‌ها | ✅ PASSED |
| ۵ | `test_anomaly_high_for_off_distribution` | ناهنجاری بالا برای توزیع خارجی | ✅ PASSED |
| ۶ | `test_picklable` | قابلیت pickle | ✅ PASSED |

### ۳.۹ فایل `test_tep_fault_detection.py` — ۷ تست (همه موفق ✅)

| # | نام تست | توصیف | وضعیت |
|---|---|---|---|
| ۱ | `test_fit_returns_metrics` | fit شاخص برمی‌گرداند | ✅ PASSED |
| ۲ | `test_detect_returns_results` | detect نتایج برمی‌گرداند | ✅ PASSED |
| ۳ | `test_fault_detection_rate` | نرخ تشخیص خطا (FDR) | ✅ PASSED |
| ۴ | `test_not_fitted_raises` | خطای not fitted | ✅ PASSED |
| ۵ | `test_picklable` | قابلیت pickle | ✅ PASSED |
| ۶ | `test_real_tep_pipeline_runs` | اجرای پایپ‌لاین واقعی TEP | ✅ PASSED |
| ۷ | `test_pipeline_end_to_end_real` | پایپ‌لاین کامل واقعی | ✅ PASSED |

---

## ۴. تحلیل توزیع تست‌ها بر اساس نوع

### ۴.۱ توزیع بر اساس فایل تست

| فایل تست | تعداد | درصد |
|---|---|---|
| `test_quality_production.py` | ۳۶ | ۳۱.۶٪ |
| `test_benchmark_features.py` | ۲۹ | ۲۵.۴٪ |
| `test_api.py` | ۸ | ۷.۰٪ |
| `test_dynamic_risk.py` | ۸ | ۷.۰٪ |
| `test_barrier_health.py` | ۷ | ۶.۱٪ |
| `test_integration.py` | ۷ | ۶.۱٪ |
| `test_tep_fault_detection.py` | ۷ | ۶.۱٪ |
| `test_alarm_analytics.py` | ۶ | ۵.۳٪ |
| `test_sequence_prediction.py` | ۶ | ۵.۳٪ |
| **کل** | **۱۱۴** | **۱۰۰٪** |

### ۴.۲ توزیع بر اساس نوع تست

| نوع تست | تعداد | توضیح |
|---|---|---|
| تست‌های واحد (Unit) | ~۸۰ | منطق هر ماژول به‌صورت مجزا |
| تست‌های یکپارچگی (Integration) | ۷ | پایپ‌لاین کامل end-to-end |
| تست‌های API | ۸ | endpointهای REST |
| تست‌های پیکربندی/ثابت | ~۱۹ | اهداف EEMUA، SIL، OEE و قوانین |

---

## ۵. تحلیل خطوط پوشش‌نداده‌شده

### ۵.۱ خطوط پوشش‌نداده‌شده هر ماژول

| ماژول | تعداد خطوط پوشش‌نداده | خطوط خاص |
|---|---|---|
| `config.py` | ۰ | — (کامل) |
| `tep_fault_detection.py` | ۱ | L115 (مسیر نادر predict) |
| `sequence_prediction.py` | ۳ | L185، L191، L202 (edge cases) |
| `alarm_analytics.py` | ۲۲ | مسیرهای edge case تحلیل آلارم |
| `barrier_health.py` | ۱۳ | مسیرهای edge case LOPA |
| `quality_optimizer.py` | ۲۵ | مسیرهای نادر SPC/Cpk |
| `production_optimizer.py` | ۲۲ | مسیرهای edge case OEE |
| `dynamic_risk.py` | ۲۱ | مسیرهای fallback Weibull |
| **کل** | **۱۰۷** | **۷٪ از کل کد** |

### ۵.۲ توصیه‌های افزایش coverage

برای رسیدن به coverage ≥ ۹۸٪، خطوط زیر باید پوشش داده شوند:
- **`dynamic_risk.py` (85%):** افزودن تست برای مسیرهای fallback Weibull و محاسبه stress
- **`production_optimizer.py` (89%):** افزودن تست برای edge case‌های OEE و suggest_optimizations
- **`quality_optimizer.py` (92%):** افزودن تست برای مسیرهای نادر Cpk و Ishikawa RCA

---

## ۶. اجرای تست

دستور اجرای تست با coverage:

```bash
cd /home/z/my-project/inno-ghadir-petrochemical-shasta
python -m pytest tests/ --cov=src/bham --cov-report=term --cov-report=html --cov-report=xml
```

خروجی:
```
============================= 114 passed in 10.42s =============================
TOTAL    1446    107    93%
Coverage HTML written to dir reports/coverage_html
Coverage XML written to file reports/coverage.xml
```

---

## ۷. نتیجه‌گیری

| شاخص | نتیجه |
|---|---|
| **نرخ موفقیت تست** | **۱۰۰٪** (۱۱۴/۱۱۴) ✅ |
| **نرخ هم‌پوشانی کلی** | **۹۳٪** ✅ |
| **بالاترین coverage ماژول** | `config.py` و `tep_fault_detection.py` (۹۹-۱۰۰٪) |
| **پایین‌ترین coverage ماژول** | `dynamic_risk.py` (۸۵٪) — همچنان بالای آستانه صنعتی |
| **زمان اجرا** | ۱۰.۴۲ ثانیه |
| **وضعیت کلی** | ✅ **ممتاز** — آماده استقرار عملیاتی |

### مزایای پیکربندی تست فعلی
۱. **پوشش جامع:** ۹۳٪ از ۱٬۴۴۶ خط کد پوشش داده شده
۲. **تنوع تست:** واحد، یکپارچگی، API و پیکربندی
۳. **سرعت بالا:** ۱۱۴ تست در کمتر از ۱۱ ثانیه
۴. **قابلیت اطمینان:** صفر تست ناموفق
۵. **گزارش‌گیری:** خروجی HTML و XML برای تحلیل دقیق‌تر

### توصیه‌های فاز بعدی
- افزودن تست برای ۱۰۷ خط باقی‌مانده (هدف: coverage ≥ ۹۸٪)
- افزودن تست‌های performance/load برای API
- افزودن تست‌های fuzzing برای ورودی‌های نامعتبر
- راه‌اندازی CI/CD برای اجرای خودکار تست‌ها در هر commit
