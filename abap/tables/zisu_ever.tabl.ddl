@EndUserText.label : 'IS-U mock: utility contract'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
@AbapCatalog.tableCategory : #TRANSPARENT
@AbapCatalog.deliveryClass : #A
@AbapCatalog.dataMaintenance : #RESTRICTED
define table zisu_ever {
  key client : abap.clnt not null;
  key vertrag : abap.char(10) not null;
  vkont : abap.char(12);
  anlage : abap.char(10);
  einzdat : abap.dats;
  auszdat : abap.dats;
}
