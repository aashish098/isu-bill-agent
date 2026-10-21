@AccessControl.authorizationCheck: #NOT_REQUIRED
@EndUserText.label: 'IS-U mock: device installation history'
define view entity ZI_ISU_DeviceHistory
  as select from zisu_egerh as g
    inner join   zisu_ever  as v on v.anlage = g.anlage
{
  key g.equnr  as Device,
  key g.anlage as Installation,
      v.vkont  as ContractAccount,
      g.sernr  as SerialNumber,
      g.ab     as ValidFrom,
      g.bis    as ValidTo,
      g.faktor as Factor
}
