function sendTrigger(lj, value)
%Send trigger to EEG via LPT2
% LPT2 port 1: 7416
%portNo = 7416;
%lptwrite(portNo,value);
%WaitSecs(0.002);  
%lptwrite(portNo,0);

% todo - need LabJack U3 series
lj.sendTrigger(value);
WaitSecs(0.002); % wait 2 ms (500 Hz)
lj.sendTrigger(0);

return
