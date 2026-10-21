@EndUserText.label : 'IS-U mock: meter reading results'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
@AbapCatalog.tableCategory : #TRANSPARENT
@AbapCatalog.deliveryClass : #A
@AbapCatalog.dataMaintenance : #RESTRICTED
define table zisu_eabl {
  key client : abap.clnt not null;
  key ablbelnr : abap.char(12) not null;
  equnr : abap.char(18);
  adat : abap.dats;
  zwstand : abap.dec(17,1);
  istablart : abap.char(2);
  ablesgr : abap.char(2);
}
