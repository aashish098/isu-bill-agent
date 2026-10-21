@EndUserText.label : 'IS-U mock: business partner'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
@AbapCatalog.tableCategory : #TRANSPARENT
@AbapCatalog.deliveryClass : #A
@AbapCatalog.dataMaintenance : #RESTRICTED
define table zisu_but000 {
  key client : abap.clnt not null;
  key partner : abap.char(10) not null;
  name : abap.char(40);
  city : abap.char(40);
}
