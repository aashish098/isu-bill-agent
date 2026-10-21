@EndUserText.label: 'IS-U Bill Anomaly Agent - data service'
define service ZUI_ISU_BILLAGENT {
  expose ZI_ISU_Account           as Account;
  expose ZI_ISU_BillingDocument   as BillingDocument;
  expose ZI_ISU_BillingLine       as BillingLine;
  expose ZI_ISU_MeterRead         as MeterRead;
  expose ZI_ISU_DeviceHistory     as DeviceHistory;
  expose ZI_ISU_RatePrice         as RatePrice;
  expose ZI_ISU_ClarificationCase as ClarificationCase;
}
