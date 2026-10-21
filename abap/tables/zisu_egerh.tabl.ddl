@EndUserText.label : 'IS-U mock: device history'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
@AbapCatalog.tableCategory : #TRANSPARENT
@AbapCatalog.deliveryClass : #A
@AbapCatalog.dataMaintenance : #RESTRICTED
define table zisu_egerh {
  key client : abap.clnt not null;
  key equnr : abap.char(18) not null;
  key anlage : abap.char(10) not null;
  sernr : abap.char(18);
  ab : abap.dats;
  bis : abap.dats;
  faktor : abap.dec(9,3);
}
