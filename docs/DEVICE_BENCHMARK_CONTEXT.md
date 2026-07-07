
Fit Group(
	Bivariate(
		Y( :SMP_RATE ),
		X( :PERIOD_END ),
		Fit Where(
			:DEVICE == "PNCB",
			Fit Spline( 0.1, Standardized, {Line Color( "Red" )} )
		),
		Fit Where(
			:DEVICE == "PXMG",
			Fit Spline( 0.1, Standardized, {Line Color( "Green" )} )
		),
		Fit Where(
			:DEVICE == "PXSA",
			Fit Spline( 0.1, Standardized, {Line Color( "Blue" )} )
		),
		Fit Where(
			:DEVICE == "PXSB",
			Fit Spline( 0.1, Standardized, {Line Color( "Orange" )} )
		),
		Fit Where(
			:DEVICE == "PYZA",
			Fit Spline( 0.1, Standardized, {Line Color( "BlueGreen" )} )
		),
		Fit Where(
			:DEVICE == "X78C",
			Fit Spline( 0.1, Standardized, {Line Color( "Purple" )} )
		),
		Fit Where(
			:DEVICE == "X78D",
			Fit Spline( 0.1, Standardized, {Line Color( "Yellow" )} )
		),
		SendToReport(
			Dispatch(
				{},
				"PERIOD_END",
				ScaleBox,
				{Min( 3818534400 ), Max( 3866579712 ), Interval( "Week" ), Inc( 4 ),
				Minor Ticks( 0 ), Label Row(
					{Label Orientation( "Angled" ), Show Major Grid( 1 ),
					Show Minor Grid( 1 )}
				)}
			),
			Dispatch(
				{},
				"SMP_RATE",
				ScaleBox,
				{Min( -0.05 ), Max( 0.7 ), Inc( 0.1 ), Minor Ticks( 3 ),
				Label Row( {Show Major Grid( 1 ), Show Minor Grid( 1 )} )}
			),
			Dispatch(
				{},
				"Bivar Plot",
				FrameBox,
				{Frame Size( 436, 363 ), Row Legend(
					:DEVICE,
					Color( 1 ),
					Color Theme( "JMP Vibrant"(1) ),
					Marker( 1 ),
					Marker Theme( "Standard" ),
					Continuous Scale( 0 ),
					Reverse Scale( 0 ),
					Excluded Rows( 0 )
				)}
			)
		)
	),
	Bivariate(
		Y( :BEEP_RATE ),
		X( :PERIOD_END ),
		Fit Where(
			:DEVICE == "PNCB",
			Fit Spline( 0.1, Standardized, {Line Color( "Red" )} )
		),
		Fit Where(
			:DEVICE == "PXMG",
			Fit Spline( 0.1, Standardized, {Line Color( "Green" )} )
		),
		Fit Where(
			:DEVICE == "PXSA",
			Fit Spline( 0.1, Standardized, {Line Color( "Blue" )} )
		),
		Fit Where(
			:DEVICE == "PXSB",
			Fit Spline( 0.1, Standardized, {Line Color( "Orange" )} )
		),
		Fit Where(
			:DEVICE == "PYZA",
			Fit Spline( 0.1, Standardized, {Line Color( "BlueGreen" )} )
		),
		Fit Where(
			:DEVICE == "X78C",
			Fit Spline( 0.1, Standardized, {Line Color( "Purple" )} )
		),
		Fit Where(
			:DEVICE == "X78D",
			Fit Spline( 0.1, Standardized, {Line Color( "Yellow" )} )
		),
		SendToReport(
			Dispatch(
				{},
				"PERIOD_END",
				ScaleBox,
				{Min( 3818534400 ), Max( 3866579712 ), Interval( "Week" ), Inc( 4 ),
				Minor Ticks( 0 ), Label Row(
					{Label Orientation( "Angled" ), Show Major Grid( 1 ),
					Show Minor Grid( 1 )}
				)}
			),
			Dispatch(
				{},
				"BEEP_RATE",
				ScaleBox,
				{Min( -0.05 ), Max( 0.7 ), Inc( 0.1 ), Minor Ticks( 3 ),
				Label Row( {Show Major Grid( 1 ), Show Minor Grid( 1 )} )}
			),
			Dispatch(
				{},
				"Bivar Plot",
				FrameBox,
				{Frame Size( 436, 363 ), Row Legend(
					DEVICE,
					Color( 1 ),
					Color Theme( "JMP Vibrant"(1) ),
					Marker( 1 ),
					Marker Theme( "Standard" ),
					Continuous Scale( 0 ),
					Reverse Scale( 0 ),
					Excluded Rows( 0 )
				)}
			)
		)
	),
	Bivariate(
		Y( :SAMPLE_SIZE ),
		X( :PERIOD_END ),
		Fit Where(
			:DEVICE == "PNCB",
			Fit Spline( 0.1, Standardized, {Line Color( "Red" )} )
		),
		Fit Where(
			:DEVICE == "PXMG",
			Fit Spline( 0.1, Standardized, {Line Color( "Green" )} )
		),
		Fit Where(
			:DEVICE == "PXSA",
			Fit Spline( 0.1, Standardized, {Line Color( "Blue" )} )
		),
		Fit Where(
			:DEVICE == "PXSB",
			Fit Spline( 0.1, Standardized, {Line Color( "Orange" )} )
		),
		Fit Where(
			:DEVICE == "PYZA",
			Fit Spline( 0.1, Standardized, {Line Color( "BlueGreen" )} )
		),
		Fit Where(
			:DEVICE == "X78C",
			Fit Spline( 0.1, Standardized, {Line Color( "Purple" )} )
		),
		Fit Where(
			:DEVICE == "X78D",
			Fit Spline( 0.1, Standardized, {Line Color( "Yellow" )} )
		),
		SendToReport(
			Dispatch(
				{},
				"PERIOD_END",
				ScaleBox,
				{Min( 3818534400 ), Max( 3866579712 ), Interval( "Week" ), Inc( 4 ),
				Minor Ticks( 0 ), Label Row(
					{Label Orientation( "Angled" ), Show Major Grid( 1 ),
					Show Minor Grid( 1 )}
				)}
			),
			Dispatch(
				{},
				"SAMPLE_SIZE",
				ScaleBox,
				{Label Row( {Show Major Grid( 1 ), Show Minor Grid( 1 )} )}
			),
			Dispatch(
				{},
				"Bivar Plot",
				FrameBox,
				{Frame Size( 436, 363 ), Row Legend(
					DEVICE,
					Color( 1 ),
					Color Theme( "JMP Vibrant"(1) ),
					Marker( 1 ),
					Marker Theme( "Standard" ),
					Continuous Scale( 0 ),
					Reverse Scale( 0 ),
					Excluded Rows( 0 )
				)}
			)
		)
	),
	<<{Arrange in Rows( 3 )},
	Where( :LAYER == "8M5CL" )
);

## Ad Hoc Generation Workflow

1. Refresh the benchmark CSV outputs (writes both dated output and CURRENT_BENCHMARK.csv):

	c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe BE_QUERY_FILES/modular_processor/EXTEND_BENCHMARK.py

2. Generate the plotting JSL from CURRENT_BENCHMARK.csv:

	c:/Users/tbatson/My Programs/SQLPathFinder3/Python3/python.exe BE_QUERY_FILES/modular_processor/GENERATE_DEVICE_BENCHMARK_JSL.py

3. Open and run:

	outputs/benchmarks/DEVICE_BENCHMARK_PLOT.jsl

Expected chart behavior from generated JSL:

- Three charts: SMP_RATE, BEEP_RATE, SAMPLE_SIZE
- By-group by LAYER (8M5CL and 8M6CL)
- Row legend by DEVICE with Color Theme("JMP Vibrant"(1))
- 4-week ticks on PERIOD_END axis (Interval("Week"), Inc(4))
- SMP_RATE and BEEP_RATE axis limits fixed to Min(-0.01), Max(0.75)
- Spline controls hidden via Fit Spline(..., {Report(0)}) with BorderBox collapse fallback
