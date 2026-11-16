"""Validação de contornos pequenos na grade longitude/latitude usada pelo CAR."""

from math import hypot, isfinite, radians, sin

EPS = 1e-9
EARTH_RADIUS_M = 6371008.8


def edges(ring):
    return zip(ring, ring[1:])


def cross(u, v):
    return u[0] * v[1] - u[1] * v[0]


def subtract(a, b):
    return a[0] - b[0], a[1] - b[1]


def dot(u, v):
    return u[0] * v[0] + u[1] * v[1]


def intersection_parameters(a, b, c, d):
    """Retorna as posições da interseção no segmento a–b, entre 0 e 1."""
    u, v, w = subtract(b, a), subtract(d, c), subtract(c, a)
    lu, lv = hypot(*u), hypot(*v)
    if min(lu, lv) <= EPS:
        return ()
    denominator = cross(u, v)
    if abs(denominator) > EPS * max(lu, lv):
        t, s = cross(w, v) / denominator, cross(w, u) / denominator
        if -EPS <= t <= 1 + EPS and -EPS <= s <= 1 + EPS:
            return (min(1, max(0, t)),)
    elif abs(cross(w, u)) <= EPS * lu:
        p, q = sorted((dot(w, u) / dot(u, u), dot(subtract(d, a), u) / dot(u, u)))
        start, end = max(0, p), min(1, q)
        if start <= end:
            return start, end
    return ()


def point_location(point, ring):
    """Distingue exterior (-1), limite (0) e interior (1)."""
    x, y = point
    inside = False
    for a, b in edges(ring):
        u, v = subtract(b, a), subtract(point, a)
        length = hypot(*u)
        if length <= EPS:
            continue
        if abs(cross(u, v)) <= EPS * length and -EPS * length <= dot(u, v) <= dot(u, u) + EPS * length:
            return 0
        if (a[1] > y) != (b[1] > y) and x < a[0] + (y - a[1]) * u[0] / u[1]:
            inside = not inside
    return 1 if inside else -1


def segment_samples(a, b, boundary):
    # Entre duas interseções consecutivas, a relação com o polígono é constante.
    parameters = {0, 1}
    for c, d in boundary:
        parameters.update(intersection_parameters(a, b, c, d))
    stops = sorted(parameters)
    yield a
    for left, right in zip(stops, stops[1:]):
        if right - left > EPS:
            t = (left + right) / 2
            yield a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])


def signed_double_area(ring):
    origin = ring[0]
    return sum(cross(subtract(a, origin), subtract(b, origin)) for a, b in edges(ring))


def overlaps(first, second):
    # Contornos no mesmo sentido têm interiores do mesmo lado de uma aresta coincidente.
    first = first if signed_double_area(first) > 0 else first[::-1]
    second = second if signed_double_area(second) > 0 else second[::-1]
    boundary = list(edges(second))
    for a, b in edges(first):
        for c, d in boundary:
            match = intersection_parameters(a, b, c, d)
            if len(match) == 2 and match[1] - match[0] > EPS and dot(subtract(b, a), subtract(d, c)) > 0:
                return True
        if any(point_location(point, second) == 1 for point in segment_samples(a, b, boundary)):
            return True
    boundary = list(edges(first))
    return any(point_location(point, first) == 1 for a, b in edges(second)
               for point in segment_samples(a, b, boundary))


def inside_property(ring, geometry):
    polygons = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        polygons = [polygons]
    for outer, *holes in polygons:
        boundary = [edge for part in (outer, *holes) for edge in edges(part)]
        if all(point_location(point, outer) >= 0 for a, b in edges(ring)
               for point in segment_samples(a, b, boundary)) and not any(overlaps(ring, hole) for hole in holes):
            return True
    return False


def parse_ring(raw):
    if not isinstance(raw, list) or not 4 <= len(raw) <= 129:
        raise ValueError("Desenhe um contorno fechado com 3 a 128 pontos.")
    ring = []
    for point in raw:
        if (not isinstance(point, list) or len(point) != 2
                or any(type(value) not in (int, float) for value in point)):
            raise ValueError("Ponto inválido no contorno.")
        lon, lat = point
        if not (-180 <= lon <= 180 and -85 <= lat <= 85 and isfinite(lon) and isfinite(lat)):
            raise ValueError("Ponto fora dos limites do mapa.")
        ring.append((lon, lat))
    if ring[0] != ring[-1] or len(set(ring[:-1])) != len(ring) - 1:
        raise ValueError("Feche o contorno sem repetir pontos intermediários.")

    segments = list(edges(ring))
    for index, (a, b) in enumerate(segments):
        if hypot(*subtract(b, a)) <= EPS or abs(b[0] - a[0]) >= 180:
            raise ValueError("O contorno contém uma aresta inválida.")
        for other in range(index + 1, len(segments)):
            shared_vertex = other == index + 1 or (index == 0 and other == len(segments) - 1)
            match = intersection_parameters(a, b, *segments[other])
            if (match and not shared_vertex) or (len(match) == 2 and match[1] - match[0] > EPS):
                raise ValueError("O contorno cruza a si mesmo. Mova os pontos e tente novamente.")
    if abs(signed_double_area(ring)) < EPS**2:
        raise ValueError("O contorno precisa cobrir uma área acima de zero.")
    return ring


def validate_plot(raw, property_geometry, other_plots):
    ring = parse_ring(raw)
    if property_geometry and not inside_property(ring, property_geometry):
        raise ValueError("O talhão precisa ficar inteiro dentro do perímetro do CAR.")
    integral = sum(radians(b[0] - a[0]) * (sin(radians(a[1])) + sin(radians(b[1]))) for a, b in edges(ring))
    area = abs(integral) * EARTH_RADIUS_M**2 / 20000
    return {
        "area_ha": round(area, 4),
        "sobreposicoes": [key for key, raw_ring in other_plots.items() if overlaps(ring, parse_ring(raw_ring))],
    }
