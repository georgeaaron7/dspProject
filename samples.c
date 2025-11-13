% --- Read audio file ---
[file, path] = uigetfile({'*.mp3;*.wav', 'Audio Files'}, 'Select audio file');
if isequal(file, 0)
    disp('User cancelled');
    return;
end

filename = fullfile(path, file);
[x, fs] = audioread(filename);

% --- Convert to mono if stereo ---
if size(x, 2) > 1
    x = mean(x, 2);
end

% --- Display basic info ---
fprintf('File: %s\nSampling rate: %d Hz\nDuration: %.2f sec\n', file, fs, length(x)/fs);

% --- Extract a non-silent section (e.g., 1s starting at 10s) ---
start_time = 10; % seconds into the song
duration = 1;    % seconds to export
start_idx = round(start_time * fs);
end_idx = start_idx + round(duration * fs) - 1;
end_idx = min(end_idx, length(x));

segment = x(start_idx:end_idx);

% --- Normalize to -1..1 ---
segment = segment / max(abs(segment));

% --- Write C array ---
fid = fopen('sound_samples.c', 'w');
fprintf(fid, 'const float sound_samples[%d] = {\n', length(segment));
fprintf(fid, '%.6ff,\n', segment);
fprintf(fid, '};\n');
fclose(fid);

disp('✅ Export complete! File: sound_samples.c');
