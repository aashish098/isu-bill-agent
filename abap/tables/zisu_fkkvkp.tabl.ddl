@EndUserText.label : 'IS-U mock: contract account'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
@AbapCatalog.tableCategory : #TRANSPARENT
@AbapCatalog.deliveryClass : #A
@AbapCatalog.dataMaintenance : #RESTRICTED
define table zisu_fkkvkp {
  key client : abap.clnt not null;
  key vkont : abap.char(12) not null;
  partner : abap.char(10);
}
