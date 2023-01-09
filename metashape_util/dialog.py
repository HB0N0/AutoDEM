class Dialog:
	def __init__(self, app):
		self.app = app

	def getListCoice(self, list, title = "Wähle eine Option", default = 1):
		dialog_text = title + "\n\n"
		i = 1
		for li in list:
			dialog_text += (str(i) + ":  " + li + "\n")
			i += 1
		input = self.app.getInt(dialog_text, default)
		if not isinstance(input, int):
			raise Exception(("\"{}\" wurde abgebrochen").format(title))
		selectedIndex = input - 1
		if selectedIndex >= len(list):
			input = len(list)
		if selectedIndex < 0:
			input = 0
		return list[selectedIndex]