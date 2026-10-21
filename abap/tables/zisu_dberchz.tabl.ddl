@EndUserText.label : 'IS-U mock: billing document lines'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
@AbapCatalog.tableCategory : #TRANSPARENT
@AbapCatalog.deliveryClass : #A
@AbapCatalog.dataMaintenance : #RESTRICTED
define table zisu_dberchz {
  key client : abap.clnt not null;
  key belnr : abap.char(12) not null;
  key belzeile : abap.int4 not null;
  line_type : abap.char(10);
  ab : abap.dats;
  bis : abap.dats;
  quantity : abap.dec(15,2);
  unit : abap.char(5);
  price : abap.dec(11,5);
  @Semantics.amount.currencyCode : 'zisu_dberchz.waers'
  amount : abap.curr(15,2);
  waers : abap.cuky;
}
