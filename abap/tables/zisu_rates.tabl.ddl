@EndUserText.label : 'IS-U mock: energy price per rate category'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
@AbapCatalog.tableCategory : #TRANSPARENT
@AbapCatalog.deliveryClass : #A
@AbapCatalog.dataMaintenance : #RESTRICTED
define table zisu_rates {
  key client : abap.clnt not null;
  key tariftyp : abap.char(10) not null;
  key ab : abap.dats not null;
  bis : abap.dats;
  energy_price : abap.dec(11,5);
}
