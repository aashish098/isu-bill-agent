@EndUserText.label : 'IS-U mock: billing document header'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
@AbapCatalog.tableCategory : #TRANSPARENT
@AbapCatalog.deliveryClass : #A
@AbapCatalog.dataMaintenance : #RESTRICTED
define table zisu_erch {
  key client : abap.clnt not null;
  key belnr : abap.char(12) not null;
  vertrag : abap.char(10);
  abrdats : abap.dats;
  abrdate : abap.dats;
  kwh : abap.dec(15,1);
  @Semantics.amount.currencyCode : 'zisu_erch.waers'
  net_amount : abap.curr(15,2);
  @Semantics.amount.currencyCode : 'zisu_erch.waers'
  vat_amount : abap.curr(15,2);
  @Semantics.amount.currencyCode : 'zisu_erch.waers'
  gross_amount : abap.curr(15,2);
  waers : abap.cuky;
  stokz : abap.char(1);
  reversed_by : abap.char(12);
  created_on : abap.dats;
}
