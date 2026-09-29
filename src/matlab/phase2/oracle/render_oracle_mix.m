function [oracleRaw, lookups, diagnostics] = render_oracle_mix(monoStems, subject, conditionName, requestedAzimuthsDeg, requestedElevationDeg, maximumMismatchDeg)
%RENDER_ORACLE_MIX Compatibility wrapper for the shared Phase 2 renderer.

[oracleRaw, lookups, diagnostics] = render_stem_mix( ...
    monoStems, subject, conditionName, requestedAzimuthsDeg, ...
    requestedElevationDeg, maximumMismatchDeg);
end
