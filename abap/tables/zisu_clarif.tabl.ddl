@EndUserText.label : 'IS-U mock: bill clarification case'
@AbapCatalog.enhancement.category : #NOT_EXTENSIBLE
@AbapCatalog.tableCategory : #TRANSPARENT
@AbapCatalog.deliveryClass : #A
@AbapCatalog.dataMaintenance : #RESTRICTED
define table zisu_clarif {
  key client : abap.clnt not null;
  key case_uuid : sysuuid_x16 not null;
  vkont : abap.char(12);
  belnr : abap.char(12);
  category : abap.char(20);
  summary : abap.char(255);
  status : abap.char(10);
  created_by : abp_creation_user;
  created_at : abp_creation_tstmpl;
  local_last_changed_at : abp_locinst_lastchange_tstmpl;
}
