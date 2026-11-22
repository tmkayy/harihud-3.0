// enum PinCorner_e 
// {
// 	PIN_TOPLEFT = 0,
// 	PIN_TOPRIGHT,
// 	PIN_BOTTOMLEFT,
// 	PIN_BOTTOMRIGHT,

// 	// For sibling pinning
// 	PIN_CENTER_TOP,
// 	PIN_CENTER_RIGHT,
// 	PIN_CENTER_BOTTOM,
// 	PIN_CENTER_LEFT,
// };

Resource/UI/HudPasstimePassNotify.res
{
	HudPasstimePassNotify
	{
		ControlName 				EditablePanel
		fieldName 					HudPasstimePassNotify
		xpos 						0
		ypos 						16
		zpos 						0
		wide 						f0
		tall 						480
		visible 					1
		enabled 					1
	}

	TextBox
	{
		ControlName 				EditablePanel
		fieldName 					TextBox
		xpos 						c-150
		ypos 						c-180
		zpos 						1
		wide 						300
		tall 						56
		visible 					1
		enabled 					1
		border						TFFatLineBorderRedBG
		RoundedCorners				255

		TextInPassRange
		{
			ControlName 			CExLabel
			"fgcolor_override"	"black_bright_hari"
			fieldName 				TextInPassRange
			font 					"TF2Secondary18"
			xpos 					0
			ypos 					0
			zpos 					3
			wide 					300
			tall 					32
			visible 				1
			enabled 				1
			centerwrap				1
			textAlignment 			center
			labelText 				#Msg_PasstimeInPassRange
		}

		TextLockedOn
		{
			ControlName 			CExLabel
			"fgcolor_override"	"black_bright_hari"
			fieldName 				TextLockedOn
			font 					"TF2Secondary18"
			xpos 					0
			ypos 					0
			zpos 					3
			wide 					300
			tall 					40
			visible 				1
			enabled 				1
			centerwrap				1
			textAlignment 			center
			labelText 				#Msg_PasstimeLockedOn
		}

		TextPassIncoming
		{
			ControlName 			CExLabel
			"fgcolor_override"	"black_bright_hari"
			fieldName 				TextPassIncoming
			font 					"TF2Secondary18"
			xpos 					0
			ypos 					4
			zpos 					3
			wide 					300
			tall 					32
			visible 				1
			enabled 				1
			centerwrap				1
			textAlignment 			center
			labelText 				#Msg_PasstimePassIncoming
		}

		TextPlayerName
		{
			ControlName 			CExLabel
			"fgcolor_override"	"black_bright_hari"
			fieldName 				TextPlayerName
			font 					"TF2Secondary14"
			xpos 					0
			ypos 					40
			zpos 					3
			wide 					300
			tall 					16
			visible 				1
			enabled 				1
			textAlignment 			center
			labelText 				"WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW"
		}	
	}

	PassLockIndicator
	{
		ControlName 				ImagePanel
		fieldName 					PassLockIndicator
		xpos 						-8
		ypos 						14
		wide 						64
		zpos 						3
		tall 						64
		visible 					1
		enabled 					1
		scaleImage 					1
		image 						"../passtime/hud/passtime_ball_reticle_incomingpass"
		pin_to_sibling 				TextBox
		pin_corner_to_sibling 		0
		pin_to_sibling_corner 		1
	}

	SpeechIndicator
	{
		ControlName 				ImagePanel
		fieldName 					SpeechIndicator
		xpos 						8
		ypos 						8
		zpos 						3
		wide 						48
		tall 						48
		visible 					1
		enabled 					1
		scaleImage 					1
		image 						"../passtime/hud/passtime_pass_to_me_prompt"
		pin_to_sibling 				TextBox
		pin_corner_to_sibling 		1
		pin_to_sibling_corner 		0
	}
}
