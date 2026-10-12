"""Validate a separately configured virtual panel layout."""
def validate_layout(layout):
    if not isinstance(layout, dict):
        raise ValueError('Expected layout object')
    panels = layout.get('positionData')
    if not isinstance(panels, list) or not 1 <= len(panels) <= 128:
        raise ValueError('Expected 1 to 128 panels')
    side = layout.get('sideLength')
    if type(side) is not int or not 1 <= side <= 65535:
        raise ValueError('Invalid panel side length')
    ids = set()
    for panel in panels:
        if not isinstance(panel, dict) or set(panel) != {'panelId', 'x', 'y', 'o', 'shapeType'}:
            raise ValueError('Invalid panel fields')
        if any(type(v) is not int for v in panel.values()):
            raise ValueError('Panel fields must be integers')
        if not 1 <= panel['panelId'] <= 65535 or panel['panelId'] in ids:
            raise ValueError('Invalid or duplicate panel identifier')
        if not all(-2147483648 <= panel[k] <= 2147483647 for k in ('x', 'y')):
            raise ValueError('Invalid coordinates')
        if not 0 <= panel['o'] < 360 or panel['shapeType'] != 7:
            raise ValueError('Expected virtual hexagon panel')
        ids.add(panel['panelId'])
    if layout.get('numPanels') != len(panels):
        raise ValueError('Panel count mismatch')
    return layout


def default_layout():
    return {'numPanels': 9, 'sideLength': 67, 'positionData': [
        {'panelId': index+1, 'x': (index%3)*200, 'y': (index//3)*174,
         'o': 0, 'shapeType': 7} for index in range(9)]}
