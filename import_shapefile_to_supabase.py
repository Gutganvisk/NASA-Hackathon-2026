"""
Script de Importação de Shapefiles do SICAR para o Supabase (PostgreSQL + PostGIS).
Lê diretamente os arquivos .shp e .dbf baixados do SICAR (sem dependências pesadas como GDAL).
"""

import json
import os
import struct
import sys
import urllib.request
from typing import Any, Dict, Generator, List, Tuple

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def read_dbf_records(dbf_path: str) -> Generator[Dict[str, Any], None, None]:
    """
    Lê registros de um arquivo DBF no formato xBase/ESRI em Python puro.
    """
    with open(dbf_path, "rb") as f:
        header = f.read(32)
        num_records = int.from_bytes(header[4:8], "little")
        len_header = int.from_bytes(header[8:10], "little")
        len_record = int.from_bytes(header[10:12], "little")

        fields = []
        while f.tell() < len_header - 1:
            fdesc = f.read(32)
            if fdesc[0] == 0x0D:
                break
            name = fdesc[:11].split(b"\x00")[0].decode("latin1")
            typ = chr(fdesc[11])
            length = fdesc[16]
            fields.append((name, typ, length))

        f.seek(len_header)
        for _ in range(num_records):
            rec = f.read(len_record)
            if len(rec) < len_record:
                break
            if rec[0] == 0x2A:  # Registro excluído
                continue

            pos = 1
            row = {}
            for name, typ, length in fields:
                val = rec[pos : pos + length].strip().decode("latin1", errors="ignore")
                row[name] = val
                pos += length
            yield row


def read_shp_polygons(shp_path: str) -> Generator[List[List[Tuple[float, float]]], None, None]:
    """
    Lê geometrias de polígonos (ShapeType 5) em Python puro.
    Retorna uma lista de anéis (rings) de coordenadas (lon, lat).
    """
    with open(shp_path, "rb") as f:
        header = f.read(100)
        file_length = struct.unpack(">I", header[24:28])[0] * 2

        while f.tell() < file_length:
            rec_header = f.read(8)
            if len(rec_header) < 8:
                break
            rec_num, content_len = struct.unpack(">II", rec_header)
            data = f.read(content_len * 2)
            if len(data) < 4:
                continue

            stype = struct.unpack("<I", data[:4])[0]
            if stype == 0:  # Null shape
                yield []
                continue

            if stype != 5:  # Espera Polygon
                yield []
                continue

            num_parts, num_points = struct.unpack("<II", data[36:44])
            parts = struct.unpack(f"<{num_parts}I", data[44 : 44 + 4 * num_parts])
            pts_offset = 44 + 4 * num_parts

            points = []
            for i in range(num_points):
                x, y = struct.unpack("<dd", data[pts_offset + i * 16 : pts_offset + (i + 1) * 16])
                points.append((round(x, 6), round(y, 6)))

            # Separa os anéis
            rings = []
            for p_idx in range(num_parts):
                start = parts[p_idx]
                end = parts[p_idx + 1] if p_idx + 1 < num_parts else num_points
                rings.append(points[start:end])

            yield rings


def polygon_to_wkt(rings: List[List[Tuple[float, float]]]) -> str:
    """
    Converte anéis de coordenadas para WKT (Well-Known Text) MultiPolygon.
    """
    if not rings:
        return "SRID=4326;MULTIPOLYGON EMPTY"

    parts_wkt = []
    for ring in rings:
        pts_str = ", ".join(f"{lon} {lat}" for lon, lat in ring)
        parts_wkt.append(f"(({pts_str}))")

    return f"SRID=4326;MULTIPOLYGON({', '.join(parts_wkt)})"


def parse_and_export_geojson(
    shp_path: str,
    dbf_path: str,
    output_json_path: str,
    max_records: int = 1000,
    municipio_filtro: Optional[str] = None,
    target_car: Optional[str] = "RR-1400175-3772D7A9BD394DA195CD145D10183419"
) -> int:
    """
    Processa os arquivos Shapefile e exporta uma base de dados local em JSON.
    """
    print(f"[INFO] Lendo Shapefile: {shp_path}")
    print(f"[INFO] Lendo DBF: {dbf_path}")

    dbf_gen = read_dbf_records(dbf_path)
    shp_gen = read_shp_polygons(shp_path)

    items = []
    count = 0

    for attr, rings in zip(dbf_gen, shp_gen):
        if not rings or not attr.get("cod_imovel"):
            continue

        cod = attr.get("cod_imovel", "").strip()
        mun = attr.get("municipio", "Não Identificado")

        # Filtro por município ou target CAR
        if municipio_filtro and municipio_filtro.lower() not in mun.lower() and cod != target_car:
            continue

        try:
            area_ha = float(attr.get("num_area") or attr.get("area") or 0.0)
        except ValueError:
            area_ha = 0.0

        try:
            mod_fiscais = float(attr.get("mod_fiscal") or attr.get("m_fiscal") or 0.0)
        except ValueError:
            mod_fiscais = 0.0

        # No bioma Amazônia (Roraima), Reserva Legal é ~80% e Consolidada ~20%
        reserva_ha = round(area_ha * 0.80, 4)
        consolidada_ha = round(area_ha * 0.20, 4)

        # Centróide
        all_pts = [pt for ring in rings for pt in ring]
        c_lon = round(sum(p[0] for p in all_pts) / len(all_pts), 6) if all_pts else 0.0
        c_lat = round(sum(p[1] for p in all_pts) / len(all_pts), 6) if all_pts else 0.0

        coordinates = [[list(pt) for pt in ring] for ring in rings]

        item = {
            "cod_imovel": cod,
            "municipio": mun,
            "uf": attr.get("cod_estado") or attr.get("uf", "RR"),
            "status_imovel": attr.get("ind_status") or attr.get("status_imo", "AT"),
            "tipo_imovel": attr.get("ind_tipo") or attr.get("tipo_imove", "IRU"),
            "modulos_fiscais": mod_fiscais,
            "area_total_ha": area_ha,
            "area_total_m2": round(area_ha * 10000, 2),
            "area_consolidada_ha": consolidada_ha,
            "area_consolidada_m2": round(consolidada_ha * 10000, 2),
            "area_reserva_legal_ha": reserva_ha,
            "area_reserva_legal_m2": round(reserva_ha * 10000, 2),
            "centroid": {"latitude": c_lat, "longitude": c_lon},
            "geojson": {
                "type": "Feature",
                "geometry": {
                    "type": "MultiPolygon" if len(rings) > 1 else "Polygon",
                    "coordinates": [coordinates] if len(rings) > 1 else coordinates
                },
                "properties": {
                    "cod_imovel": cod,
                    "area_ha": area_ha,
                    "area_m2": round(area_ha * 10000, 2),
                    "municipio": mun,
                    "uf": attr.get("cod_estado") or attr.get("uf", "RR"),
                    "centroid": {"latitude": c_lat, "longitude": c_lon}
                }
            }
        }

        items.append(item)
        count += 1
        if count >= max_records:
            break

    with open(output_json_path, "w", encoding="utf-8") as out_f:
        json.dump(items, out_f, ensure_ascii=False, indent=2)

    print(f"[SUCESSO] {count} imóveis rurais extraídos e salvos em {output_json_path}!")
    return count


def upload_imoveis_to_supabase(
    shp_path: str,
    dbf_path: str,
    municipio_filtro: Optional[str] = "Boa Vista",
    target_car: str = "RR-1400175-3772D7A9BD394DA195CD145D10183419",
    max_records: int = 500,
    batch_size: int = 50
) -> Dict[str, Any]:
    """
    Lê o Shapefile e envia em lotes diretamente para a tabela propriedades_rurais no Supabase via PostgREST.
    """
    from supabase_client import _supabase_request, is_supabase_configured

    if not is_supabase_configured():
        return {"sucesso": False, "erro": "Supabase não configurado no .env."}

    print(f"[SUPABASE] Iniciando extração e upload para Supabase...")
    dbf_gen = read_dbf_records(dbf_path)
    shp_gen = read_shp_polygons(shp_path)

    batch = []
    total_enviados = 0

    for attr, rings in zip(dbf_gen, shp_gen):
        if not rings or not attr.get("cod_imovel"):
            continue

        cod = attr.get("cod_imovel", "").strip()
        mun = attr.get("municipio", "Não Identificado")

        if municipio_filtro and municipio_filtro.lower() not in mun.lower() and cod != target_car:
            continue

        try:
            area_ha = float(attr.get("num_area") or attr.get("area") or 0.0)
        except ValueError:
            area_ha = 0.0

        try:
            mod_fiscais = float(attr.get("mod_fiscal") or attr.get("m_fiscal") or 0.0)
        except ValueError:
            mod_fiscais = 0.0

        consolidada_ha = round(area_ha * 0.20, 4)

        all_pts = [pt for ring in rings for pt in ring]
        c_lon = round(sum(p[0] for p in all_pts) / len(all_pts), 6) if all_pts else 0.0
        c_lat = round(sum(p[1] for p in all_pts) / len(all_pts), 6) if all_pts else 0.0

        coordinates = [[list(pt) for pt in ring] for ring in rings]

        record = {
            "cod_car": cod,
            "nome": f"Imóvel Rural {mun}",
            "municipio": mun,
            "uf": attr.get("cod_estado") or attr.get("uf", "RR"),
            "area_total_ha": area_ha,
            "area_consolidada_ha": consolidada_ha,
            "geojson": {
                "type": "Feature",
                "geometry": {
                    "type": "MultiPolygon" if len(rings) > 1 else "Polygon",
                    "coordinates": [coordinates] if len(rings) > 1 else coordinates
                },
                "properties": {
                    "cod_imovel": cod,
                    "area_ha": area_ha,
                    "municipio": mun,
                    "centroid": {"latitude": c_lat, "longitude": c_lon}
                }
            }
        }

        batch.append(record)

        if len(batch) >= batch_size:
            try:
                _supabase_request(
                    "propriedades_rurais",
                    method="POST",
                    data=batch,
                    prefer="resolution=merge-duplicates"
                )
                total_enviados += len(batch)
                print(f"[SUPABASE] Lote de {len(batch)} enviado com sucesso! Total: {total_enviados}")
            except Exception as e:
                print(f"[ERRO SUPABASE] Falha no lote: {e}")
            batch = []

        if total_enviados >= max_records:
            break

    if batch:
        try:
            _supabase_request(
                "propriedades_rurais",
                method="POST",
                data=batch,
                prefer="resolution=merge-duplicates"
            )
            total_enviados += len(batch)
            print(f"[SUPABASE] Último lote de {len(batch)} enviado! Total final: {total_enviados}")
        except Exception as e:
            print(f"[ERRO SUPABASE] Falha no último lote: {e}")

    return {"sucesso": True, "total_enviados": total_enviados}


if __name__ == "__main__":
    download_dir = r"c:\Users\ADMIN\Downloads\AREA_IMOVEL"
    shp = os.path.join(download_dir, "AREA_IMOVEL_1.shp")
    dbf = os.path.join(download_dir, "AREA_IMOVEL_1.dbf")
    out = os.path.join(os.path.dirname(__file__), "imoveis_rr_sample.json")

    if not os.path.exists(shp):
        default_dir = os.path.expandvars(r"%USERPROFILE%\Downloads\RR_IMOVEIS_Out2026")
        shp = os.path.join(default_dir, "sicar_imoveis_rr.shp")
        dbf = os.path.join(default_dir, "sicar_imoveis_rr.dbf")

    if os.path.exists(shp) and os.path.exists(dbf):
        # 1. Exporta GeoJSON local
        parse_and_export_geojson(shp, dbf, out, max_records=500, municipio_filtro="Boa Vista")
        # 2. Upload para Supabase
        upload_imoveis_to_supabase(shp, dbf, municipio_filtro="Boa Vista", max_records=500, batch_size=50)
    else:
        print("Arquivos Shapefile não encontrados no caminho padrão de Downloads.")

