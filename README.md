# eunma-traffic-monitor

서울시 TOPIS 실시간 교통정보를 주기적으로 수집해 누적 기록하는 저장소입니다.

- 대상: 강남구 대치동 '은마아파트입구' 교차로 (삼성로, axisCd=217)
- 수집 방향: axisDirDivCd=1(상행), axisDirDivCd=2(하행)
- 데이터: `data/traffic_log.csv`
- 오류 기록: `data/errors.log`

## CSV 컬럼

`timestamp_kst,axisDirDivCd,axisDirDivNm,stNodeNm,edNodeNm,speed,trfClsNm`
