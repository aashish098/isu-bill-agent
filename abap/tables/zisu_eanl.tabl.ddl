@EndUserText.label : 'IS-U mock: installation'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
@AbapCatalog.tableCategory : #TRANSPARENT
@AbapCatalog.deliveryClass : #A
@AbapCatalog.dataMaintenance : #RESTRICTED
define table zisu_eanl {
  key client : abap.clnt not null;
  key anlage : abap.char(10) not null;
  vstelle : abap.char(30);
  tariftyp : abap.char(10);
  sparte : abap.char(2);
}
